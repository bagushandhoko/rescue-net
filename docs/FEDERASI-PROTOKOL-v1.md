# Protokol Federasi Rescue-Net v1

Tahap 9b disiapkan untuk uji. Node instansi mengelola akun dan data operasional di backendnya sendiri. Rescue-Net (RN) mewakili instansi dengan satu RN Organization tertutup. Pertukaran dilakukan lewat HTTPS dan hanya membawa data yang diizinkan.

## Pendaftaran dan cabut akses

1. Kedua administrator tukar UUID `server_id` dan fingerprint identitas dari `GET node_info`. Cocokkan melalui saluran tepercaya. Pengembang node juga perlu menerima ID organisasi tujuan RN yang bersedia menerima permintaan bantuan.
2. Buat kunci koneksi acak 32 byte per arah. Tukar kunci melalui saluran rahasia. Simpan 64 digit hex huruf kecil di penyimpanan rahasia. Fingerprint **kunci koneksi** adalah SHA-256 dari 32 byte setelah decode hex. Fingerprint ini berbeda dari fingerprint identitas publik.
3. System Manager RN panggil `POST register_peer` dengan `server_id`, `name`, `url` HTTPS, `key_fingerprint`, `shared_secret`, `scope` (daftar DocType publik sesuai 9a) dan `organization`. Status awal `pending`. Lalu panggil `POST approve_peer` dengan `server_id`. ID organisasi bisa diberikan saat approve bila belum ada. Satu organisasi tertutup memiliki maksimal satu node yang disetujui. Node 9a yang sudah disetujui perlu ditautkan melalui approve sebelum memanggil API bertanda tangan.
4. Untuk rotasi, koordinasikan pergantian, lalu System Manager panggil `POST rotate_peer_key` dengan ID, fingerprint dan kunci koneksi baru. RN langsung menggunakan kunci baru. Lanjutkan pengiriman dari kursor yang tersimpan. Untuk mencabut akses, panggil `POST revoke_peer`. Node revoked tetap menjadi bagian audit. Jika perlu mengganti node yang dicabut, daftarkan identitas node baru.

URL Frappe langsung memakai `/api/method/rescue_net.api_federation.<metode>`. Proxy RN memakai awalan `/rescue-net-frappe`. Untuk klien contoh, isi `RN_FEDERATION_API` dengan URL direktori metode berakhiran `/api/method/rescue_net.api_federation` dan klien menambahkan **titik** serta nama metode. Klien memakai `RN_FEDERATION_PEER_ID`, `RN_FEDERATION_RECEIVER_ID` dan `RN_FEDERATION_SHARED_SECRET` dari lingkungan. Jalankan klien dengan perintah `info`, `pull --since 0`, atau `push file.json`.

## Tanda tangan

Untuk `push` dan `pull`, kirim POST JSON tanpa sesi pengguna. Header yang wajib ialah `X-RN-Peer` (UUID kanonik pemanggil), `X-RN-Timestamp` (detik Unix UTC, 10 digit, toleransi ±300 detik), `X-RN-Nonce` (hex huruf kecil 16 byte, baru untuk tiap percobaan), dan `X-RN-Signature` (HMAC-SHA256 hex huruf kecil). Sinkronkan jam kedua server.

Gabungkan baris berikut dengan LF. Setelah baris nonce, tambahkan byte body JSON yang persis dikirim. Pakai kunci hasil decode hex.

```text
RN-FEDERATION/1 push
<server_id penerima HTTP>
<X-RN-Peer>
<X-RN-Timestamp>
<X-RN-Nonce>
<byte body>
```

Untuk pull, baris pertama ialah `RN-FEDERATION/1 pull`. RN menyimpan nonce selama 601 detik, bersama untuk pull dan push. HTTPS melindungi respons.

### Vektor uji HMAC

Data di sini tetap dan khusus uji. Body vektor persis `{"events":[]}` tanpa newline akhir. Body tersebut dipakai untuk memeriksa tanda tangan.

- Kunci hex `000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f`
- Penerima `11111111-1111-4111-8111-111111111111`
- Pemanggil `22222222-2222-4222-8222-222222222222`
- Timestamp `1700000000`
- Nonce `00112233445566778899aabbccddeeff`
- Signature push `57a2c6276a2b726c41168328e4cf73ed8001039df64984e84bf067b2a477f033`

## Pull

Kirim `{"since_seq":0,"limit":100}`. Batas `limit` 1–200. Respons Frappe di `message` memuat `events`, `next_seq`, `has_more` dan `schema_version`. Simpan `next_seq` setelah halaman berhasil diolah. Halaman kosong dapat memiliki `has_more=true`. Retry dengan kursor lama dan nonce baru. Gunakan `event_id` untuk deduplikasi. Struktur dan proyeksi event publik mengikuti [9a](FEDERASI-9A.md). Jawaban bantuan dikirim sebagai event `object_type: "assistance.response"` khusus ke node asal. Payload-nya hanya `request_event_id` dan `decision`.

## Push

Kirim UTF-8 `{"events":[...]}` dengan 1–200 event dan maksimal 512 KiB. `seq` adalah nomor urut positif dari log node asal. `payload_checksum` berisi SHA-256 hex atas JSON payload dengan kunci diurutkan, escape ASCII dan tanpa spasi pemisah. Di Python gunakan `json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)`.

Respons `message.results` berurutan seperti input. Tiap hasil berisi `event_id`, `status` (`accepted`, `duplicate`, atau `rejected`) dan `reason` untuk penolakan. `receive_cursor` adalah nomor urut terbesar yang diterima, sehingga dapat melewati event yang ditolak dalam batch. Gunakan hasil per event untuk konfirmasi. Retry setelah jaringan putus atau 5xx dengan ID dan payload yang sama serta nonce baru. ID dan isi yang sudah diterima menghasilkan `duplicate`. Untuk memperbaiki event yang ditolak, buat event baru dengan ID dan nomor urut baru.

- **403** mencakup tanda tangan salah, replay, jam meleset, node belum disetujui atau dicabut, organisasi sudah terbuka, dan jenis konten atau ukuran transport yang ditolak.
- **400** dapat dihasilkan oleh parser HTTP/Frappe untuk JSON rusak. **417** menandakan validasi parameter/bentuk permintaan Frappe gagal.
- **200** berarti batch diproses. Alasan penolakan per event meliputi `invalid_event_identity`, `invalid_event_fields`, `unsupported_schema`, `event_type_denied`, `invalid_payload_fields`, `invalid_payload_value`, `menu_denied`, `checksum_mismatch`, `destination_unknown`, dan `event_id_conflict`.

## Isi data dan persetujuan

- `org.summary` menyajikan jumlah posko aktif, personel dan kebutuhan terbuka per kategori. RN menampilkan ringkasan terbaru yang dilaporkan node kepada pemilik organisasi dan System Manager. Angka tetap terpisah dari data operasional RN.
- `assistance.request` membawa tujuan organisasi RN, kategori, jumlah dan deskripsi kebutuhan umum. Pemilik tujuan atau System Manager dapat menerima atau menolak melalui `respond_assistance`. Keputusan dicatat satu kali dan dapat diambil melalui pull.
- `sitrep.summary`, `need.published` dan `menu.record` masuk kotak masuk untuk ditinjau. `menu.record` membawa jumlah catatan dan ID menu TERBUKA yang tersedia bagi template node. Menu bersama berlaku bagi semua template. Catatan detail tetap di backend instansi.
- Kirim hanya kebutuhan sipil dan agregat yang sudah diperiksa. Dilarang mengirim nama, kontak, identitas korban, informasi medis individu, rincian OPORD, RFL, posisi atau pergerakan militer, lampiran, kredensial, dan data TERBATAS atau RAHASIA. Teks deskripsi hanya untuk gambaran kebutuhan, maksimum 280 karakter. Hindari agregat yang dapat mengidentifikasi individu atau kelompok kecil.
- Pemilik organisasi atau System Manager dapat membaca 100 entri terbaru melalui `GET inbox?organization=<ID>`. Gunakan parameter opsional `event_type` untuk memfilter satu jenis event. Alasan penolakan tersimpan tanpa payload asli yang ditolak.

## JSON Schema

Skema berikut memakai Draft 2020-12. Server juga memeriksa checksum, bentuk UUID kanonik, kebijakan menu sesuai template dan keberadaan organisasi tujuan.

```json
{
  "type": "object",
  "properties": {
    "events": {
      "type": "array",
      "minItems": 1,
      "maxItems": 200,
      "items": {
        "$ref": "#/$defs/event"
      }
    }
  },
  "required": [
    "events"
  ],
  "additionalProperties": false,
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "uuid": {
      "type": "string",
      "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    },
    "category": {
      "enum": [
        "pangan",
        "air",
        "kesehatan",
        "shelter",
        "sanitasi",
        "transportasi",
        "lainnya"
      ]
    },
    "description": {
      "type": "string",
      "minLength": 1,
      "maxLength": 280
    },
    "count": {
      "type": "integer",
      "minimum": 0,
      "maximum": 10000000
    },
    "quantity": {
      "type": "integer",
      "minimum": 1,
      "maximum": 10000000
    },
    "event": {
      "type": "object",
      "properties": {
        "event_id": {
          "$ref": "#/$defs/uuid"
        },
        "seq": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9223372036854775807
        },
        "event_type": {
          "enum": [
            "assistance.request",
            "org.summary",
            "sitrep.summary",
            "need.published",
            "menu.record"
          ]
        },
        "schema_version": {
          "type": "integer",
          "const": 1
        },
        "payload": {
          "type": "object"
        },
        "payload_checksum": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        }
      },
      "required": [
        "event_id",
        "seq",
        "event_type",
        "schema_version",
        "payload",
        "payload_checksum"
      ],
      "additionalProperties": false,
      "oneOf": [
        {
          "properties": {
            "event_type": {
              "const": "assistance.request"
            },
            "payload": {
              "$ref": "#/$defs/assistance.request"
            }
          }
        },
        {
          "properties": {
            "event_type": {
              "const": "org.summary"
            },
            "payload": {
              "$ref": "#/$defs/org.summary"
            }
          }
        },
        {
          "properties": {
            "event_type": {
              "const": "sitrep.summary"
            },
            "payload": {
              "$ref": "#/$defs/sitrep.summary"
            }
          }
        },
        {
          "properties": {
            "event_type": {
              "const": "need.published"
            },
            "payload": {
              "$ref": "#/$defs/need.published"
            }
          }
        },
        {
          "properties": {
            "event_type": {
              "const": "menu.record"
            },
            "payload": {
              "$ref": "#/$defs/menu.record"
            }
          }
        }
      ]
    },
    "assistance.request": {
      "type": "object",
      "properties": {
        "destination": {
          "type": "string",
          "minLength": 1,
          "maxLength": 140
        },
        "category": {
          "$ref": "#/$defs/category"
        },
        "quantity": {
          "$ref": "#/$defs/quantity"
        },
        "description": {
          "$ref": "#/$defs/description"
        }
      },
      "required": [
        "destination",
        "category",
        "quantity",
        "description"
      ],
      "additionalProperties": false
    },
    "org.summary": {
      "type": "object",
      "properties": {
        "active_posts": {
          "$ref": "#/$defs/count"
        },
        "personnel": {
          "$ref": "#/$defs/count"
        },
        "open_needs": {
          "type": "object",
          "propertyNames": {
            "$ref": "#/$defs/category"
          },
          "additionalProperties": {
            "$ref": "#/$defs/count"
          }
        }
      },
      "required": [
        "active_posts",
        "personnel",
        "open_needs"
      ],
      "additionalProperties": false
    },
    "sitrep.summary": {
      "type": "object",
      "properties": {
        "active_posts": {
          "$ref": "#/$defs/count"
        },
        "open_needs": {
          "type": "object",
          "propertyNames": {
            "$ref": "#/$defs/category"
          },
          "additionalProperties": {
            "$ref": "#/$defs/count"
          }
        }
      },
      "required": [
        "active_posts",
        "open_needs"
      ],
      "additionalProperties": false
    },
    "need.published": {
      "type": "object",
      "properties": {
        "category": {
          "$ref": "#/$defs/category"
        },
        "quantity": {
          "$ref": "#/$defs/quantity"
        },
        "description": {
          "$ref": "#/$defs/description"
        }
      },
      "required": [
        "category",
        "quantity",
        "description"
      ],
      "additionalProperties": false
    },
    "menu.record": {
      "type": "object",
      "properties": {
        "menu_id": {
          "enum": [
            "status-keadaan-darurat",
            "klaster-nasional",
            "peringatan-dini",
            "zeni-akses",
            "sar-militer",
            "kesehatan-lapangan",
            "satgana-relawan",
            "asesmen-cepat-pmi",
            "donor-darah",
            "dukungan-psikososial",
            "wash",
            "gudang-regional-pmi",
            "mitra-gerakan",
            "rapat-koordinasi",
            "bantuan-antarinstansi",
            "klasifikasi-informasi",
            "komunikasi"
          ]
        },
        "record_count": {
          "$ref": "#/$defs/count"
        }
      },
      "required": [
        "menu_id",
        "record_count"
      ],
      "additionalProperties": false
    },
    "assistance.response": {
      "type": "object",
      "properties": {
        "request_event_id": {
          "$ref": "#/$defs/uuid"
        },
        "decision": {
          "enum": [
            "accept",
            "decline"
          ]
        }
      },
      "required": [
        "request_event_id",
        "decision"
      ],
      "additionalProperties": false
    }
  }
}
```
