import os

# Check where Flask would look for the database
print("DATABASE_URL from .env:")
with open('.env') as f:
    for line in f:
        if 'DATABASE_URL' in line:
            print(f"  {line.strip()}")

# The actual path Flask would use
print("\nFlask-SQLAlchemy default behavior:")
print("  With sqlite:///tenders.db it would look in app folder")
print("  With instance/ folder it would use instance/tenders.db")

# Check actual file sizes
import glob
for f in glob.glob('**/*.db', recursive=False):
    size = os.path.getsize(f)
    print(f"  {f}: {size/1024:.1f} KB")
