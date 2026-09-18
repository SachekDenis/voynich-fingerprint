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
saved as `data/ref/<language>.conllu`. The eleven treebanks used here, with the file
prefix each one uses:

| file | treebank | prefix |
|---|---|---|
| latin.conllu | UD_Latin-PROIEL | la_proiel |
| ocs.conllu | UD_Old_Church_Slavonic-PROIEL | cu_proiel |
| italian.conllu | UD_Italian-ISDT | it_isdt |
| german.conllu | UD_German-GSD | de_gsd |
| greek.conllu | UD_Ancient_Greek-PROIEL | grc_proiel |
| english.conllu | UD_English-EWT | en_ewt |
| hebrew.conllu | UD_Hebrew-HTB | he_htb |
| croatian.conllu | UD_Croatian-SET | hr_set |
| spanish.conllu | UD_Spanish-AnCora | es_ancora |
| turkish.conllu | UD_Turkish-BOUN | tr_boun |
| arabic.conllu | UD_Arabic-PADT | ar_padt |

Each file is the three standard splits concatenated in the order train, dev, test:

    fetch () {   # fetch <name> <treebank-repo> <file-prefix>
      : > "data/ref/$1.conllu"
      for split in train dev test; do
        curl -sSL "https://raw.githubusercontent.com/UniversalDependencies/$2/master/$3-ud-$split.conllu" \n          >> "data/ref/$1.conllu"
      done
    }

    fetch latin   UD_Latin-PROIEL              la_proiel
    fetch ocs     UD_Old_Church_Slavonic-PROIEL cu_proiel
    fetch italian UD_Italian-ISDT              it_isdt
    # ... and the remaining eight, prefixes as in the table above

Two further corpora are plain text rather than treebanks:

| file | text | source |
|---|---|---|
| dante_it.txt | Dante, *Divina Commedia* | Project Gutenberg ebook 1012 |
| confessions_lat.txt | Augustine, *Confessiones* | The Latin Library, `augustine/conf1..13.shtml` |

Both are stripped of boilerplate, line numbers and editorial apparatus before saving.

**A note on these two.** The numbers reported for them are reproducible from the sources
above, but they are *not* the numbers an earlier revision of this repository quoted. That
revision used text files whose provenance was never recorded, and the Augustinian figure
in particular (h2 = 2.979, quoted as the closest of the thirteen) cannot be recovered from
any public source tried here. Rebuilt from the sources in the table, the closest language
is Dante at h2 = 3.125 and Augustine stands at 3.191. The conclusion is unchanged — both
are far above the manuscript's 1.893 — but the specific figure moves.


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
