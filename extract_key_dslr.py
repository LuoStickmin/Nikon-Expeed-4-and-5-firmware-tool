import sys
import extract_key as ek
import decrypt_firmware as fw

HEADER = 0          # D750: no 32-byte header, label at 0x00
ek.HDR = HEADER
fw.HDR = HEADER

if __name__ == "__main__":
    sys.exit(ek.main())
