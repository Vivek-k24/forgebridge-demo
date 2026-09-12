from __future__ import annotations

from fractions import Fraction

CATEGORY_META = {
    "wrenches-sockets": ("Wrenches & sockets", "wrench"),
    "screwdrivers-bits": ("Screwdrivers & driver bits", "screwdriver"),
    "pliers-cutters": ("Pliers & cutters", "pliers"),
    "power-tools": ("Power tools", "power"),
    "lifting-support": ("Jacks, stands & support", "jack"),
    "drilling-cutting": ("Drill bits & cutting", "drill"),
    "fluid-service": ("Fluid service", "fluid"),
    "fasteners-retainers": ("Fasteners, clips & rivets", "fastener"),
    "hose-line-service": ("Hose & line service", "hose"),
    "seals-o-rings": ("O-rings & seals", "oring"),
    "measuring-diagnostic": ("Measuring & diagnostic", "measure"),
    "shop-safety": ("Shop & safety equipment", "shop"),
    "specialty-automotive": ("Specialty automotive tools", "specialty"),
    "other": ("Other", "other"),
}

CATEGORY_LIMITS = {
    "wrenches-sockets": 240,
    "screwdrivers-bits": 150,
    "pliers-cutters": 35,
    "power-tools": 34,
    "lifting-support": 30,
    "drilling-cutting": 90,
    "fluid-service": 46,
    "fasteners-retainers": 170,
    "hose-line-service": 62,
    "seals-o-rings": 90,
    "measuring-diagnostic": 33,
    "shop-safety": 39,
    "specialty-automotive": 60,
    "other": 28,
}
EXPECTED_ITEM_COUNT = 1107


def _fraction_label(value: Fraction) -> str:
    whole = value.numerator // value.denominator
    remainder = value - whole
    if whole and remainder:
        return f"{whole}-{remainder.numerator}/{remainder.denominator}"
    if whole:
        return str(whole)
    return f"{value.numerator}/{value.denominator}"


def _slug(value: str) -> str:
    output = []
    dash = False
    for character in value.lower():
        if character.isalnum():
            output.append(character)
            dash = False
        elif not dash:
            output.append("-")
            dash = True
    return "".join(output).strip("-")


def _sample_evenly(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    if len(rows) <= limit:
        return rows
    if limit == 1:
        return [rows[0]]
    indexes = [round(index * (len(rows) - 1) / (limit - 1)) for index in range(limit)]
    return [rows[index] for index in indexes]


def build_equipment_catalog_seed() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def add(category: str, name: str, keywords: str, visual_key: str) -> None:
        rows.append(
            {
                "catalog_key": _slug(name),
                "category": category,
                "name": name,
                "keywords": keywords,
                "visual_key": visual_key,
            }
        )

    metric_sizes = list(range(4, 33))
    sae_fractions = [Fraction(value, 16) for value in range(4, 25)]

    for size in metric_sizes:
        for kind in ("Combination wrench", "Ratcheting combination wrench", "Open-end wrench", "Box-end wrench"):
            add("wrenches-sockets", f"{size} mm {kind}", "metric spanner hand wrench", "wrench")
    for fraction in sae_fractions:
        for kind in ("Combination wrench", "Ratcheting combination wrench"):
            add("wrenches-sockets", f"{_fraction_label(fraction)} in {kind}", "SAE imperial spanner hand wrench", "wrench")
    for drive, sizes in (("1/4", range(4, 15)), ("3/8", range(6, 25)), ("1/2", range(10, 33))):
        for size in sizes:
            for depth in ("standard", "deep"):
                add("wrenches-sockets", f"{drive} in drive {size} mm {depth} socket", "metric socket six point", "socket")
    for drive, fractions in (("1/4", sae_fractions[:10]), ("3/8", sae_fractions[:16]), ("1/2", sae_fractions[6:])):
        for fraction in fractions:
            for depth in ("standard", "deep"):
                add("wrenches-sockets", f"{drive} in drive {_fraction_label(fraction)} in {depth} socket", "SAE imperial socket six point", "socket")
    for drive in ("1/4", "3/8", "1/2"):
        for kind in ("ratchet", "flex-head ratchet", "breaker bar", "torque wrench"):
            add("wrenches-sockets", f"{drive} in drive {kind}", "socket wrench handle", "ratchet")
        for length in (2, 3, 4, 6, 8, 10, 12, 18, 24):
            add("wrenches-sockets", f"{drive} in drive {length} in extension", "socket extension", "extension")
    for size in (6, 8, 10, 12, 15):
        add("wrenches-sockets", f"{size} in adjustable wrench", "crescent adjustable spanner", "wrench")
    for size in range(8, 23):
        add("wrenches-sockets", f"{size} mm flare-nut wrench", "line wrench brake fuel tube", "wrench")
    for size in (8, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 24, 27, 30, 32):
        add("wrenches-sockets", f"{size} mm crowfoot wrench", "crow foot socket", "wrench")

    for number in range(5):
        for length in (3, 4, 6, 8, 12):
            add("screwdrivers-bits", f"Phillips #{number} screwdriver, {length} in shaft", "cross head screwdriver", "screwdriver")
    for number in range(4):
        for length in (3, 6, 8):
            add("screwdrivers-bits", f"JIS #{number} screwdriver, {length} in shaft", "Japanese Industrial Standard cross head screwdriver", "screwdriver")
    for width in (2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6, 6.5, 8, 10):
        for length in (3, 6, 8):
            add("screwdrivers-bits", f"{width:g} mm slotted screwdriver, {length} in shaft", "flat blade screwdriver", "screwdriver")
    torx_sizes = list(range(5, 11)) + [15, 20, 25, 27, 30, 40, 45, 50, 55, 60]
    for size in torx_sizes:
        add("screwdrivers-bits", f"Torx T{size} screwdriver", "star driver", "screwdriver")
        add("screwdrivers-bits", f"Security Torx T{size} bit", "tamper resistant star bit", "bit")
    for size in (1.5, 2, 2.5, 3, 4, 5, 6, 7, 8, 10, 12):
        add("screwdrivers-bits", f"{size:g} mm hex key", "Allen key metric", "hex")
        add("screwdrivers-bits", f"{size:g} mm hex bit socket", "Allen socket metric", "hex")
    for fraction in [Fraction(value, 64) for value in (5, 6, 7, 8, 9, 10, 12, 14, 16, 18, 20, 24, 28, 32)]:
        add("screwdrivers-bits", f"{_fraction_label(fraction)} in hex key", "Allen key SAE", "hex")
    for size in range(4, 15):
        add("screwdrivers-bits", f"{size} mm nut driver", "metric nut driver", "screwdriver")
    for fraction in sae_fractions[:12]:
        add("screwdrivers-bits", f"{_fraction_label(fraction)} in nut driver", "SAE nut driver", "screwdriver")
    for tip in ("#0", "#1", "#2", "#3", "#4"):
        add("screwdrivers-bits", f"Phillips {tip} 1 in insert bit", "driver bit", "bit")
        add("screwdrivers-bits", f"Phillips {tip} 2 in power bit", "driver bit", "bit")
    for size in (10, 15, 20, 25, 27, 30, 40, 45, 50):
        add("screwdrivers-bits", f"Torx T{size} 1 in insert bit", "star driver bit", "bit")
        add("screwdrivers-bits", f"Torx T{size} 2 in power bit", "star driver bit", "bit")
    for size in (2, 2.5, 3, 4, 5, 6, 7, 8, 10):
        add("screwdrivers-bits", f"{size:g} mm hex 1 in insert bit", "Allen driver bit", "bit")
        add("screwdrivers-bits", f"{size:g} mm hex 2 in power bit", "Allen driver bit", "bit")

    for name in (
        "Slip-joint pliers", "Tongue-and-groove pliers 8 in", "Tongue-and-groove pliers 10 in", "Tongue-and-groove pliers 12 in",
        "Needle-nose pliers 6 in", "Needle-nose pliers 8 in", "Long-reach needle-nose pliers 11 in", "Bent-nose pliers",
        "Linesman pliers", "Diagonal cutters 6 in", "Diagonal cutters 8 in", "End-cutting nippers", "Cable cutters", "Wire stripping pliers",
        "Locking pliers 5 in", "Locking pliers 7 in", "Locking pliers 10 in", "Locking C-clamp pliers",
        "Snap-ring pliers internal straight", "Snap-ring pliers internal 90 degree", "Snap-ring pliers external straight", "Snap-ring pliers external 90 degree",
        "Hose clamp pliers", "Spring clamp pliers", "CV boot clamp pliers", "Safety wire twisting pliers", "Fencing pliers", "Duckbill pliers",
        "Flat-nose pliers", "Round-nose pliers", "Hog-ring pliers", "Plastic trim clip pliers", "Push-pin removal pliers", "Brake spring pliers", "Fuel line disconnect pliers",
    ):
        add("pliers-cutters", name, "hand plier cutter gripping", "pliers")

    for power in ("cordless", "corded"):
        for tool in ("drill", "impact driver", "impact wrench", "angle grinder", "rotary tool", "reciprocating saw", "oscillating multi-tool", "polisher", "heat gun"):
            sizes = ("compact", "full-size") if power == "cordless" else ("standard",)
            for size in sizes:
                add("power-tools", f"{power.title()} {size} {tool}", "electric power tool", "power")
    for drive in ("1/4", "3/8", "1/2"):
        add("power-tools", f"Cordless {drive} in drive electric ratchet", "battery powered ratchet", "power")
    for voltage in (12, 18, 20, 24):
        add("power-tools", f"{voltage} V cordless work light", "battery LED shop light", "light")

    for tons in (1.5, 2, 2.5, 3, 3.5, 4):
        add("lifting-support", f"{tons:g} ton hydraulic floor jack", "vehicle lifting jack", "jack")
    for tons in (2, 3, 4, 6, 8, 12):
        add("lifting-support", f"{tons} ton bottle jack", "vehicle lifting jack", "jack")
        add("lifting-support", f"{tons} ton jack stand pair", "vehicle support stands", "stand")
    for capacity in (6000, 8000, 10000, 12000, 16000):
        add("lifting-support", f"{capacity} lb vehicle ramp pair", "car ramps", "ramp")
    for name in ("Rubber wheel chock pair", "Metal wheel chock pair", "Low-profile creeper", "Mechanic seat", "Engine support bar", "Transmission jack", "Motorcycle/ATV jack"):
        add("lifting-support", name, "lifting support shop", "jack")

    for half_mm in range(2, 27):
        size = half_mm / 2
        add("drilling-cutting", f"{size:g} mm HSS drill bit", "metric high speed steel drill bit", "drill")
    for number in range(1, 61):
        add("drilling-cutting", f"Number #{number} HSS drill bit", "number gauge high speed steel drill bit", "drill")
    seen_fractions: set[Fraction] = set()
    for denominator in (64, 32, 16):
        for numerator in range(1, denominator // 2 + 1):
            fraction = Fraction(numerator, denominator)
            if fraction in seen_fractions:
                continue
            seen_fractions.add(fraction)
            add("drilling-cutting", f"{_fraction_label(fraction)} in HSS drill bit", "fractional high speed steel drill bit", "drill")
    for name in (
        "Small step drill bit", "Medium step drill bit", "Large step drill bit", "Deburring tool", "Countersink bit 1/4 in", "Countersink bit 3/8 in",
        "Metal cutting wheel 3 in", "Metal cutting wheel 4-1/2 in", "Grinding wheel 4-1/2 in", "Flap disc 4-1/2 in 40 grit", "Flap disc 4-1/2 in 80 grit",
        "Bi-metal hole saw 1/2 in", "Bi-metal hole saw 3/4 in", "Bi-metal hole saw 1 in", "Bi-metal hole saw 1-1/4 in", "Bi-metal hole saw 1-1/2 in", "Bi-metal hole saw 2 in",
    ):
        add("drilling-cutting", name, "cutting drilling metal", "drill")

    for size in (54, 60, 64, 65, 67, 68, 73, 74, 75, 76, 79, 80, 82, 86, 90, 93, 95, 100, 101):
        add("fluid-service", f"{size} mm oil filter cap wrench", "oil filter socket cap", "oil")
    for name in (
        "Oil filter strap wrench", "Oil filter chain wrench", "Oil filter pliers", "Three-jaw oil filter wrench", "Drain pan 8 qt", "Drain pan 12 qt", "Drain pan 16 qt", "Drain pan 20 qt",
        "Fluid transfer pump", "Hand siphon pump", "Fluid extractor 6 L", "Fluid extractor 10 L", "Brake bleeder bottle", "Vacuum brake bleeder", "Pressure brake bleeder",
        "Coolant funnel kit", "Spill-free coolant funnel", "Transmission fluid funnel", "Long-neck funnel", "Flexible-spout funnel", "Grease gun manual", "Grease gun cordless",
        "Suction gun", "Turkey-baster style fluid syringe", "Measuring pitcher 1 qt", "Measuring pitcher 2 qt", "Measuring pitcher 5 L",
    ):
        add("fluid-service", name, "fluid oil coolant brake service", "fluid")

    pitches = {4: (0.7,), 5: (0.8,), 6: (1.0,), 8: (1.0, 1.25), 10: (1.25, 1.5), 12: (1.25, 1.5, 1.75), 14: (1.5, 2.0)}
    for diameter, diameter_pitches in pitches.items():
        for pitch in diameter_pitches:
            for length in (10, 12, 16, 20, 25, 30, 35, 40, 50, 60, 70, 80):
                add("fasteners-retainers", f"M{diameter} x {pitch:g} x {length} mm hex bolt", "metric generic bolt hardware", "bolt")
            add("fasteners-retainers", f"M{diameter} x {pitch:g} hex nut", "metric generic nut hardware", "nut")
            add("fasteners-retainers", f"M{diameter} x {pitch:g} nylon lock nut", "metric generic nyloc nut hardware", "nut")
        add("fasteners-retainers", f"M{diameter} flat washer", "metric washer hardware", "washer")
        add("fasteners-retainers", f"M{diameter} split lock washer", "metric lock washer hardware", "washer")
    for stem in (5, 6, 6.5, 7, 8, 8.5, 9, 10):
        for head in (12, 14, 16, 18, 20, 22, 25):
            add("fasteners-retainers", f"{stem:g} mm stem x {head} mm head universal push retainer", "plastic clip push pin trim fastener", "clip")
    for diameter in (2.4, 3.2, 4.0, 4.8, 6.4):
        for length in (6, 8, 10, 12, 16, 20, 25):
            add("fasteners-retainers", f"{diameter:g} x {length} mm aluminum blind rivet", "pop rivet generic", "rivet")
    for name in (
        "Universal screw-type plastic rivet", "Universal expanding plastic rivet", "Universal fir-tree retainer small", "Universal fir-tree retainer medium",
        "Universal fir-tree retainer large", "Universal bumper retainer clip", "Universal splash-shield retainer clip", "Universal interior trim retainer clip",
    ):
        add("fasteners-retainers", name, "plastic automotive trim generic fastener", "clip")

    for size in (4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 25, 28, 30, 32):
        add("hose-line-service", f"{size} mm hose pinch-off clamp", "fluid line holding clamp leak prevention", "hose")
        add("hose-line-service", f"{size} mm spring hose clamp", "hose clamp spring band", "hose")
    for low, high in ((6, 12), (8, 16), (10, 18), (12, 22), (16, 25), (20, 32), (25, 40), (32, 50), (40, 60), (50, 70), (60, 80), (70, 90), (80, 100)):
        add("hose-line-service", f"{low}-{high} mm worm-drive hose clamp", "hose clamp stainless band", "hose")
    for fraction in (Fraction(1, 4), Fraction(5, 16), Fraction(3, 8), Fraction(1, 2), Fraction(5, 8), Fraction(3, 4)):
        add("hose-line-service", f"{_fraction_label(fraction)} in line pinch-off clamp", "fluid fuel vacuum line clamp leak prevention", "hose")
    for name in (
        "3-piece flexible hose pinch pliers set", "Fuel line disconnect set", "A/C line disconnect set", "Quick-connect line release tool set", "Hose pick set",
        "90-degree hose pick", "Straight hose separator pick", "Hose removal pliers", "Tube bending pliers", "Mini tubing cutter", "Standard tubing cutter",
        "Double-flare tool kit", "Bubble-flare tool kit",
    ):
        add("hose-line-service", name, "fluid hose fuel brake AC line service", "hose")

    for cross_section in (1.5, 2.0, 2.5, 3.0, 3.5):
        for inside_diameter in range(3, 31):
            add("seals-o-rings", f"{inside_diameter} mm ID x {cross_section:g} mm cross-section O-ring", "generic metric seal o ring", "oring")
    for inside_diameter in [Fraction(value, 16) for value in range(2, 17)]:
        for cross_section in (Fraction(1, 16), Fraction(3, 32), Fraction(1, 8)):
            add("seals-o-rings", f"{_fraction_label(inside_diameter)} in ID x {_fraction_label(cross_section)} in cross-section O-ring", "generic SAE seal o ring", "oring")
    for name in ("Universal O-ring pick set", "Plastic seal pick set", "Hook and pick set", "O-ring sizing cone", "O-ring lubricant applicator"):
        add("seals-o-rings", name, "seal service tool", "oring")

    for name in (
        "Digital multimeter", "Automotive test light", "Non-contact voltage tester", "Clamp meter", "Digital caliper 6 in", "Digital caliper 12 in",
        "Feeler gauge metric/SAE", "Spark plug gap gauge", "Tire pressure gauge digital", "Tire pressure gauge pencil", "Infrared thermometer", "Contact thermometer",
        "Compression tester gasoline", "Vacuum/pressure gauge", "Fuel pressure gauge kit", "Cooling-system pressure tester", "Battery load tester", "Battery conductance tester",
        "OBD-II scan tool", "Circuit probe", "Wire piercing probe set", "Back-probe pin set", "Mechanic stethoscope", "Borescope camera", "Inspection mirror set",
        "Telescoping magnetic pickup tool", "Tape measure 25 ft", "Steel rule 12 in", "Thread pitch gauge metric", "Thread pitch gauge SAE", "Torque angle gauge",
        "Dial indicator", "Magnetic dial indicator base",
    ):
        add("measuring-diagnostic", name, "measurement diagnostic test inspection", "measure")

    for name in (
        "Safety glasses clear", "Safety glasses tinted", "Face shield", "Mechanic gloves nitrile-coated", "Disposable nitrile gloves medium", "Disposable nitrile gloves large",
        "Disposable nitrile gloves XL", "Hearing protection earmuffs", "Foam earplug pack", "Knee pad pair", "Fire extinguisher ABC", "First-aid kit", "LED headlamp",
        "Corded shop light", "Rechargeable shop light", "Magnetic work light", "Fender cover", "Shop towel pack", "Absorbent spill pads", "Oil absorbent granules",
        "Parts cleaning brush", "Wire brush brass", "Wire brush steel", "Nylon detailing brush", "Magnetic parts tray 6 in", "Magnetic parts tray 10 in",
        "Parts organizer small", "Parts organizer large", "Tool cart", "Rolling mechanic stool", "Shop vacuum wet/dry", "Portable air compressor", "Air blow gun",
        "Tire inflator", "Extension cord 25 ft", "Extension cord 50 ft", "GFCI extension cord", "Battery charger/maintainer", "Jump starter pack",
    ):
        add("shop-safety", name, "shop safety protection equipment", "shop")

    for name in (
        "Serpentine belt tool", "Ball joint separator", "Tie-rod end puller", "Pitman arm puller", "Three-jaw gear puller 3 in", "Three-jaw gear puller 6 in",
        "Two-jaw puller 3 in", "Two-jaw puller 6 in", "Bearing separator", "Slide hammer kit", "Hub puller kit", "Brake caliper piston compressor",
        "Disc brake spreader", "Brake caliper wind-back kit", "Drum brake spring tool", "Brake shoe retaining spring tool", "Brake spoon adjuster",
        "Line wrench set metric", "Line wrench set SAE", "Spark plug socket 5/8 in", "Spark plug socket 13/16 in", "Spark plug socket 14 mm",
        "Oxygen sensor socket 7/8 in", "Oxygen sensor socket 22 mm", "Lambda sensor crowfoot", "Battery terminal puller", "Battery post cleaner",
        "Trim removal tool set plastic", "Panel clip removal tool", "Upholstery clip remover", "Pickle fork small", "Pickle fork medium", "Pickle fork large",
        "Axle nut socket set", "CV axle puller", "Seal driver set", "Bearing race driver set", "Harmonic balancer puller", "Steering wheel puller",
        "Fan clutch wrench set", "Pulley holding tool", "Chain wrench", "Strap wrench", "Pry bar 8 in", "Pry bar 12 in", "Pry bar 18 in",
        "Pry bar 24 in", "Pry bar 36 in", "Dead-blow hammer 16 oz", "Dead-blow hammer 32 oz", "Ball-peen hammer 16 oz", "Ball-peen hammer 24 oz",
        "Rubber mallet 16 oz", "Brass hammer 16 oz", "Punch and chisel set", "Center punch automatic", "Thread chaser metric set", "Thread chaser SAE set",
        "Tap and die set metric", "Tap and die set SAE",
    ):
        add("specialty-automotive", name, "automotive mechanic specialty tool", "specialty")

    for name in (
        "Utility knife", "Razor scraper", "Plastic razor scraper", "Scissors", "Permanent marker black", "Paint marker white", "Paint marker yellow", "Masking tape",
        "Painter's tape", "Electrical tape", "PTFE thread seal tape", "Zip tie 4 in", "Zip tie 8 in", "Zip tie 12 in", "Zip tie 18 in", "Stainless zip tie",
        "Bungee cord 12 in", "Bungee cord 24 in", "Ratchet strap 1 in", "Ratchet strap 2 in", "Paracord 50 ft", "Mechanic wire roll", "Safety wire roll",
        "Folding work table", "Parts tray", "Small funnel set", "Flashlight", "Magnetic flashlight holder",
    ):
        add("other", name, "general workshop multipurpose", "other")

    unique: dict[str, dict[str, str]] = {}
    for row in rows:
        unique.setdefault(row["catalog_key"], row)

    grouped: dict[str, list[dict[str, str]]] = {category: [] for category in CATEGORY_META}
    for row in unique.values():
        grouped[row["category"]].append(row)

    output: list[dict[str, str]] = []
    for category in CATEGORY_META:
        output.extend(_sample_evenly(grouped[category], CATEGORY_LIMITS[category]))

    if len(output) != EXPECTED_ITEM_COUNT:
        raise RuntimeError(f"equipment seed count changed: {len(output)}")
    return output
