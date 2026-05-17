#!/usr/bin/env python3
"""Final push - delete all git history and push fresh"""

import os
import sys

os.chdir(r"C:\Users\29499\WorkBuddy\Claw\gaokao-analyzer")

print("=" * 50)
print("  Final Push - Clean Start")
print("=" * 50)
print()

# Step 1: Delete ALL scripts with tokens
print("Step 1: Remove all token-containing files...")
files = ["publish.py", "upload.py", "push.py", "cleanup_and_push.py",
         "auto-publish.bat", "傻瓜发布.bat", "一键发布.bat", "一键发布.ps1"]
for f in files:
    if os.path.exists(f):
        os.remove(f)
        print(f"  Deleted: {f}")

# Step 2: DESTROY git history (the key fix)
print("\nStep 2: Clear git history...")
if os.path.exists(".git"):
    os.system('attrib -r /s /d ".git" 2>nul')
    os.system('rmdir /s /q ".git" 2>nul')
    print("  Deleted: .git folder")

# Step 3: Get token
token = input("\nGitHub Token: ")
if not token:
    print("Token required!")
    input("Press Enter...")
    sys.exit(1)

# Step 4: Fresh git init
print("\nStep 3: Fresh git init...")
os.system("git init")
os.system("git branch -M main")
os.system('git config user.email "user@example.com"')
os.system('git config user.name "user"')

# Step 5: Add remote with token
print("Step 4: Setup remote...")
remote = f"https://shuangzhebai:{token}@github.com/shuangzhebai/gaokao-analyzer.git"
os.system(f"git remote add origin {remote}")

# Step 6: Add and commit
print("Step 5: Add files...")
os.system("git add .")
print("Step 6: Commit...")
os.system('git commit -m "feat: gaokao-analyzer v5.1"')

# Step 7: Push
print("\nStep 7: Pushing to GitHub...")
result = os.system("git push -u origin main --force")

print()
if result == 0:
    print("=" * 50)
    print("  SUCCESS! Published to:")
    print("  https://github.com/shuangzhebai/gaokao-analyzer")
    print("=" * 50)
    print("\nYou can delete this script now.")
else:
    print("FAILED!")

input("\nPress Enter to exit...")
