"""Descomprime el original para usar open() en el núcleo académico.

Utilidad de archivos; no forma parte del algoritmo que se sustenta.
"""
import gzip
from pathlib import Path

folder = Path(__file__).resolve().parent
source = folder / 'facebook-links.txt.gz'
target = folder / 'facebook-links.txt'
with gzip.open(source, 'rb') as compressed, target.open('wb') as plain:
    while True:
        block = compressed.read(1024 * 1024)
        if not block:
            break
        plain.write(block)
print(target)
