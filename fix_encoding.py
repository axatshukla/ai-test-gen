import pathlib, sys

files = [
    'src/testgen/extractor.py',
    'src/testgen/gate.py',
    'src/testgen/reporter.py',
    'src/testgen/cli.py',
    'src/testgen/clients/fake_client.py',
    'src/testgen/clients/vllm_client.py',
]

for f in files:
    p = pathlib.Path(f)
    try:
        text = p.read_text(encoding='latin-1')
        p.write_text(text, encoding='utf-8')
        print(f'Re-encoded: {f}')
    except Exception as e:
        print(f'ERROR {f}: {e}', file=sys.stderr)
