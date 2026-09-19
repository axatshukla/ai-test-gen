import pathlib
lines = open('src/testgen/cli.py', encoding='utf-8').readlines()
# Fix lines 136-137: broken write_text newline join
# line[135] (0-indexed) = '        out_path.write_text(
lines[135] = '        out_path.write_text(chr(10).join(lines), encoding=' + chr(34) + 'utf-8' + chr(34) + ')\n'
lines[136] = ''  # remove the orphaned .join(lines) line
pathlib.Path('src/testgen/cli.py').write_text(''.join(lines), encoding='utf-8')
print('Fixed lines 136-137')
