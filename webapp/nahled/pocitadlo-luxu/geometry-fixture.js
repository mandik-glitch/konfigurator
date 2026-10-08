/* Měřeno build_fixture.py; optika je výslovný předpoklad. */
globalThis.LuxGeometryFixture = {
  "version": 1,
  "units": "mm",
  "sourceParameters": {
    "sirka": 1200.0,
    "hloubka": 800.0,
    "vyska": 840.0,
    "presah": 30.0,
    "led_rameno": 560.0,
    "stojky": true,
    "police": 1,
    "kolecka": true,
    "panely": true,
    "led": true,
    "patky": false,
    "suplik": true,
    "elektrozlab": true,
    "drzak_pet": true,
    "suplik_posun": 0.0,
    "stredni_noha": null,
    "loz": false,
    "loz_rozteca": 200.0,
    "loz_okraj": 100.0,
    "vyrez1": false,
    "vyrez1_w": 200.0,
    "vyrez1_d": 150.0,
    "vyrez1_x": 100.0,
    "vyrez1_z": 100.0,
    "vyrez1_police": false,
    "vyrez2": false,
    "vyrez2_w": 200.0,
    "vyrez2_d": 150.0,
    "vyrez2_x": 100.0,
    "vyrez2_z": 360.0,
    "vyrez2_police": false,
    "vyrez3": false,
    "vyrez3_w": 200.0,
    "vyrez3_d": 150.0,
    "vyrez3_x": 100.0,
    "vyrez3_z": 620.0,
    "vyrez3_police": false
  },
  "sourceShiftMm": [
    -246.26025561523437,
    2.8588867188261702e-05,
    -142.5089
  ],
  "measurements": [
    {
      "partId": "product_4933",
      "vertices": 426,
      "minMm": [
        -417.7406384277344,
        821.536058919231,
        -564.8853920511137
      ],
      "maxMm": [
        382.2591662597659,
        839.5368098259122,
        635.11539660534
      ]
    },
    {
      "partId": "product_4933",
      "vertices": 426,
      "minMm": [
        -268.2250354003906,
        345.1860589192311,
        -564.8853920511137
      ],
      "maxMm": [
        381.77480590820306,
        363.18680982591223,
        635.11539660534
      ]
    },
    {
      "partId": "product_4929",
      "vertices": 4726,
      "minMm": [
        -205.13090454101558,
        1812.4398260498049,
        -620.0600781250002
      ],
      "maxMm": [
        -120.11802612304683,
        1893.4886541748049,
        626.9408984374998
      ]
    }
  ],
  "sourceHashes": {
    "/home/openai1/konfigurator/api/stul_konfigurator.py": "70df296565f8f3e694b82849fa9601640dec98c709d6262dd1acf4857f969689",
    "/home/openai1/konfigurator/api/stul_glb.py": "26d6e34ced4ede33877f6c60a4ae323f01b8bfdf8a83cb6a9b327e5206caa86e",
    "/home/openai1/konfigurator/api/stul_sablona_577.json": "4abc113dbd0a375353f68dffd1420247312f9d9a7f8f9561a11882db2ed41be1",
    "/home/openai1/konfigurator/ukoly/podklady/led_produkt_4929.json": "468645f78c1992c815dd347d1934bf1f925ee26eaa774c9586332114b129110b",
    "/opt/konfigurator/webapp/katalog/product_4929.glb": "19ca8b99786a11eba2b83642c5f15be66d5e1b91cfee500f97d9d8c028ee07eb",
    "/opt/konfigurator/webapp/katalog/product_4933.glb": "de7f3d9c07c9385bcd910e7e163d8f2f60f893c1a24334fe175287597bef5aae"
  },
  "workplane": {
    "originMm": [
      -417.7406384277344,
      839.5368098259122,
      -564.8853920511137
    ],
    "axisU": [
      0,
      0,
      1
    ],
    "axisV": [
      1,
      0,
      0
    ],
    "normal": [
      0,
      1,
      0
    ],
    "widthMm": 1200.0007886564538,
    "depthMm": 799.9998046875003
  },
  "lights": [
    {
      "id": "LED1200-1",
      "productId": 4929,
      "sku": "LED1200",
      "type": "linear",
      "luminousFluxLm": 3960,
      "powerW": 33,
      "housingLengthMm": 1247.0,
      "nominalLengthMm": 1200,
      "beamAngleDeg": null,
      "cctK": null,
      "criRa": null,
      "photometryFile": null,
      "maintenanceFactor": null,
      "geometryStatus": "hypothesis",
      "startMm": [
        -162.6244653320312,
        1812.4398260498049,
        -596.5595898437502
      ],
      "endMm": [
        -162.6244653320312,
        1812.4398260498049,
        603.4404101562498
      ],
      "direction": [
        0,
        -1,
        0
      ],
      "housingBoundsMm": [
        [
          -205.13090454101558,
          1812.4398260498049,
          -620.0600781250002
        ],
        [
          -120.11802612304683,
          1893.4886541748049,
          626.9408984374998
        ]
      ],
      "distribution": {
        "kind": "cosine_power",
        "exponent": 1,
        "status": "hypothesis",
        "source": "CIE S 017:2020 17-24-062; scénář, nikoli vlastnost LED1200"
      }
    }
  ]
};
