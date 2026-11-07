import struct

with open('c.png', 'rb') as f:
    data = f.read()

# Parse IHDR to get dimensions
pos = 8
while pos < len(data):
    length = struct.unpack('>I', data[pos:pos+4])[0]
    chunk_type = data[pos+4:pos+8]
    if chunk_type == b'IHDR':
        w = struct.unpack('>I', data[pos+8:pos+12])[0]
        h = struct.unpack('>I', data[pos+12:pos+16])[0]
        del data
        print(f'Original: {w}x{h}')
        # We can't easily downscale PNG without PIL
        # Use scrcpy's max-size instead
        break
    pos += 12 + length
