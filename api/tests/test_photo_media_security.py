import unittest
from io import BytesIO
from unittest.mock import patch

from PIL import Image

from partgraph.repair_experience.memory.storage import (
    PhotoFormatError,
    PhotoResourceLimitError,
    prepare_photo,
)


def _image_bytes(
    image_format: str,
    *,
    size: tuple[int, int] = (24, 16),
    mode: str = "RGB",
    exif: Image.Exif | None = None,
) -> bytes:
    image = Image.new(mode, size, (80, 120, 160, 180) if mode == "RGBA" else (80, 120, 160))
    output = BytesIO()
    kwargs: dict[str, object] = {}
    if exif is not None:
        kwargs["exif"] = exif
    image.save(output, format=image_format, **kwargs)
    return output.getvalue()


class PhotoMediaSecurityTests(unittest.IsolatedAsyncioTestCase):
    async def test_supported_raster_formats_survive_full_decode_and_sanitization(self) -> None:
        cases = (
            ("JPEG", "image/jpeg", "jpg"),
            ("PNG", "image/png", "png"),
            ("WEBP", "image/webp", "webp"),
        )
        for image_format, media_type, extension in cases:
            with self.subTest(image_format=image_format):
                prepared = await prepare_photo(
                    _image_bytes(image_format),
                    maximum_bytes=4 * 1024 * 1024,
                )
                self.assertEqual(prepared.media_type, media_type)
                self.assertEqual(prepared.extension, extension)
                self.assertEqual((prepared.width, prepared.height), (24, 16))
                with Image.open(BytesIO(prepared.data)) as decoded:
                    decoded.load()
                    self.assertEqual(decoded.size, (24, 16))

    async def test_heic_is_fully_decoded_and_normalized_to_metadata_free_jpeg(self) -> None:
        prepared = await prepare_photo(
            _image_bytes("HEIF"),
            maximum_bytes=4 * 1024 * 1024,
        )
        self.assertEqual(prepared.media_type, "image/jpeg")
        self.assertEqual(prepared.extension, "jpg")
        with Image.open(BytesIO(prepared.data)) as decoded:
            decoded.load()
            self.assertEqual(decoded.format, "JPEG")
            self.assertFalse(decoded.getexif())

    async def test_truncated_and_header_only_images_are_rejected(self) -> None:
        valid_jpeg = _image_bytes("JPEG")
        bad_inputs = (
            valid_jpeg[:-24],
            b"\xff\xd8\xff" + b"not-a-real-jpeg",
            b"\x89PNG\r\n\x1a\n" + b"not-a-real-png",
            b"RIFF\x00\x00\x00\x00WEBPnot-a-real-webp",
        )
        for data in bad_inputs:
            with self.subTest(prefix=data[:12]):
                with self.assertRaises(PhotoFormatError):
                    await prepare_photo(data, maximum_bytes=4 * 1024 * 1024)

    async def test_dimension_limit_is_enforced_before_persistence(self) -> None:
        with patch(
            "partgraph.repair_experience.memory.storage.MAX_PHOTO_DIMENSION",
            8,
        ):
            with self.assertRaises(PhotoResourceLimitError):
                await prepare_photo(
                    _image_bytes("PNG", size=(9, 2)),
                    maximum_bytes=4 * 1024 * 1024,
                )

    async def test_decoded_pixel_limit_is_enforced_before_persistence(self) -> None:
        with patch(
            "partgraph.repair_experience.memory.storage.MAX_PHOTO_PIXELS",
            63,
        ):
            with self.assertRaises(PhotoResourceLimitError):
                await prepare_photo(
                    _image_bytes("PNG", size=(8, 8)),
                    maximum_bytes=4 * 1024 * 1024,
                )

    async def test_multi_frame_webp_is_rejected(self) -> None:
        first = Image.new("RGB", (12, 12), (255, 0, 0))
        second = Image.new("RGB", (12, 12), (0, 255, 0))
        output = BytesIO()
        first.save(
            output,
            format="WEBP",
            save_all=True,
            append_images=[second],
            duration=100,
            loop=0,
        )
        with self.assertRaises(PhotoFormatError):
            await prepare_photo(output.getvalue(), maximum_bytes=4 * 1024 * 1024)

    async def test_exif_is_removed_including_the_container_that_can_hold_gps(self) -> None:
        exif = Image.Exif()
        exif[315] = "PartGraph fixture photographer"
        exif[270] = "privacy-sensitive fixture metadata"
        source = _image_bytes("JPEG", exif=exif)
        self.assertIn(b"PartGraph fixture photographer", source)

        prepared = await prepare_photo(source, maximum_bytes=4 * 1024 * 1024)
        self.assertNotIn(b"PartGraph fixture photographer", prepared.data)
        self.assertNotIn(b"privacy-sensitive fixture metadata", prepared.data)
        with Image.open(BytesIO(prepared.data)) as decoded:
            self.assertFalse(decoded.getexif())
            self.assertNotIn("exif", decoded.info)
            self.assertNotIn("xmp", decoded.info)
            self.assertNotIn("icc_profile", decoded.info)

    async def test_valid_image_with_trailing_polyglot_bytes_is_reencoded_without_tail(self) -> None:
        marker = b"<script>polyglot-tail</script>"
        source = _image_bytes("JPEG") + marker
        prepared = await prepare_photo(source, maximum_bytes=4 * 1024 * 1024)
        self.assertNotIn(marker, prepared.data)
        with Image.open(BytesIO(prepared.data)) as decoded:
            decoded.load()
            self.assertEqual(decoded.format, "JPEG")

    async def test_sanitized_output_must_still_fit_the_storage_byte_ceiling(self) -> None:
        source = _image_bytes("PNG", size=(64, 64))
        with self.assertRaises(PhotoResourceLimitError):
            await prepare_photo(source, maximum_bytes=16)


if __name__ == "__main__":
    unittest.main()
