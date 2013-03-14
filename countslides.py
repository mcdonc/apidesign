f = open('presentation.rst')
lines = 0
for line in f:
    if line.startswith('---'):
       lines += 1
print lines
