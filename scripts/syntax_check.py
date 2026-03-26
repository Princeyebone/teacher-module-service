import ast, os

ROOT = r"c:\Users\HP\tmdl5"
errors = []

for dp, dn, fn in os.walk(os.path.join(ROOT, "app")):
    for f in fn:
        if not f.endswith(".py"):
            continue
        fpath = os.path.join(dp, f)
        try:
            src = open(fpath, encoding="utf-8").read()
        except UnicodeDecodeError:
            src = open(fpath, encoding="latin-1").read()
        try:
            ast.parse(src)
        except SyntaxError as e:
            errors.append(f"{os.path.relpath(fpath, ROOT)} : {e}")

if errors:
    print(f"\nERRORS: {len(errors)} syntax error(s) found:")
    for err in errors:
        print(" -", err)
else:
    print("OK: All files are syntax-clean!")
