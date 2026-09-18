# Data

The transcriptions are not redistributed here; download them from the source.

    mkdir -p data/ref
    cd data
    for f in IT2a-n.txt GC2a-n.txt ZL3b-n.txt VT0e-n.txt RF1b-e.txt FG2a-n.txt 000_README.txt; do
      curl -sSLO "https://www.voynich.nu/data/$f"
    done

`IT2a-n.txt` (Takahashi, EVA) is the one used for everything in the README.
`GC2a-n.txt` (Currier, v101) is the one-glyph-one-character alphabet used for the
robustness check. The others are independent transliterations of the same text.

Reference corpora come from Universal Dependencies, one CoNLL-U file per language,
saved as `data/ref/<language>.conllu`:

| file | treebank |
|---|---|
| latin.conllu | UD_Latin-PROIEL |
| ocs.conllu | UD_Old_Church_Slavonic-PROIEL |
| italian.conllu | UD_Italian-ISDT |
| german.conllu | UD_German-GSD |
| czech.conllu | UD_Czech-PDT |
| greek.conllu | UD_Ancient_Greek-PROIEL |
| english.conllu | UD_English-EWT |
| hebrew.conllu | UD_Hebrew-HTB |
| croatian.conllu | UD_Croatian-SET |
| spanish.conllu | UD_Spanish-AnCora |
| turkish.conllu | UD_Turkish-BOUN |
| arabic.conllu | UD_Arabic-PADT |

Only the FORM column is read.

## IVTFF notes

Two conventions in `voynich_lib.py` matter:

- Locus codes starting with `L` or `R` are **labels**: short texts beside figures, radial
  text in the zodiac. They are excluded from the body-text analysis and studied
  separately by `label_analysis.py`.
- `$L` gives Currier's language A/B; `$H` gives Fagin Davis's hand.

## Split used throughout

Training: even-numbered leaves. Test: odd-numbered leaves. `freeze_and_verify.py`
also runs the reverse split as a check against selection bias.
