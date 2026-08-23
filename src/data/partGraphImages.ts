export interface PartPreviewImage {
  url: string;
  sourcePageUrl: string;
  alt: string;
}

// V0 uses remote product photos from the same source pages already used to
// corroborate OEM identity. They are intentionally not copied into the repo.
// Production image rights, caching and hot-link reliability still need a
// dedicated source/licensing policy.
export const partImageById: Record<string, PartPreviewImage> = {
  radiator: {
    url: 'https://www.hondapartsnow.com/resources/encry/actual-picture/hpn/large/ebfbd200d74317d06a8eec0aa7a1efb8/4b01ec8b1e521455baf37cfc8384d65c.jpg',
    sourcePageUrl: 'https://www.hondapartsnow.com/genuine/honda~radiator~19010-rrh-901.html',
    alt: 'Honda 19010-RRH-901 radiator product photo',
  },
  'upper-brackets': {
    url: 'https://www.hondapartsnow.com/resources/encry/actual-picture/hpn/large/9a000f0b1a048dc4517af70291323a98/b7afecce312e5776e74b3787f3a05ee5.jpg',
    sourcePageUrl: 'https://www.hondapartsnow.com/genuine/honda~bracket~radiator~mount~74171-sna-a00.html',
    alt: 'Honda 74171-SNA-A00 upper radiator mounting bracket product photo',
  },
  'upper-cushions': {
    url: 'https://www.hondapartsnow.com/resources/encry/actual-picture/hpn/large/d4669a98b8ac2e757d39989517a77d5b/8186ca5be44334674ea967079fef2841.jpg',
    sourcePageUrl: 'https://www.hondapartsnow.com/genuine/honda~cushion~radiator~mounting~74173-SJ4-000.html',
    alt: 'Honda 74173-SJ4-000 upper radiator mounting cushion product photo',
  },
  'mount-bolts': {
    url: 'https://www.hondapartsnow.com/resources/encry/actual-picture/hpn/large/909d069c4314b6b20145f0deed191424/a4b05902b7d99469ea88d78a6d36c856.jpg',
    sourcePageUrl: 'https://www.hondapartsnow.com/genuine/honda~bolt~washer~93405-06016-04.html',
    alt: 'Honda 93405-06016-04 bolt-washer product photo',
  },
  'water-temp-sensor': {
    url: 'https://www.hondapartsnow.com/resources/encry/actual-picture/hpn/large/0f5282a4e08d3cfa6172833c1ece379a/ffca0654ffb1cc8c814d92b639a9dba6.jpg',
    sourcePageUrl: 'https://www.hondapartsnow.com/genuine/honda~sensor~assy~37870-rta-005.html',
    alt: 'Honda 37870-RTA-005 water temperature sensor product photo',
  },
  'drain-bolt': {
    url: 'https://www.hondapartsnow.com/resources/encry/actual-picture/hpn/large/ac67aa9cb3bc5c010c4add5abd957e68/1041c781560e3b5f66fb0e800390288d.jpg',
    sourcePageUrl: 'https://www.hondapartsnow.com/genuine/honda~bolt~drain~19011-ph1-621.html',
    alt: 'Honda 19011-PH1-621 radiator drain bolt product photo',
  },
  condenser: {
    url: 'https://www.hondapartsnow.com/resources/encry/actual-picture/hpn/large/bd42ad578aa479ecf1916a757a6e51b1/1d2fcaecddfafc9f90658d8b3d110733.jpg',
    sourcePageUrl: 'https://www.hondapartsnow.com/genuine/honda~condenser~80110-sna-a42.html',
    alt: 'Honda 80110-SNA-A42 condenser product photo',
  },
};
