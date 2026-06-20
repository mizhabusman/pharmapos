from image_processor import optimize_for_upload

with open("test.jpg", "rb") as f:
    original = f.read()

compressed = optimize_for_upload(original)

with open("compressed.jpg", "wb") as f:
    f.write(compressed)

print(f"Original: {len(original)/1024:.2f} KB")
print(f"Compressed: {len(compressed)/1024:.2f} KB")