# Assessment of two claims encountered in 2026

Neither is a decipherment. Both were examined because the requests that led to this
repository started from them, and both are refuted by their own material or by simple
measurements.

---

## 1. A camera-obscura encoding with an Old Church Slavonic reading

**The claim.** A public repository (`crknftart/VoynichManuscript`) and its accompanying
paper in the *Rose+Croix Journal* (Vol. 13) argue that the manuscript was produced by
projecting an original document through a camera obscura and tracing the inverted
image, that the result must therefore be read right to left, and that the language is
Old Church Slavonic written in a cursive Glagolitic hand.

**What the method actually is.** The paper's own description of the "reverse camera
obscura process" is: *"Digitally scanned images of the manuscript were first reflected
vertically along the X-axis and then horizontally reflected along the Y-axis"* — a
180° rotation of the page image, followed by deriving an alphabet by eye from stroke
paths. No key, no substitution table, no test.

**Four findings against it.**

1. **The paper states that no translation exists.** Its conclusion: *"This singular and
   combined alphabet has shown promising leads, but will require additional papers and
   an expert in languages of the time period for an accurate translation."* The README
   later claims the language and even the subject matter (neurons, reproductive
   anatomy); the paper does not support either.

2. **The central artefact is missing.** Both READMEs describe a folder of "unobscured"
   high-contrast scans that the method depends on. It is not in the repository.

3. **A file in the repository refutes the method.** `MS408-10v-LINES1 copy.jpg` shows
   one line of the manuscript in six variants. **The same character sequence is given
   six different English translations**, differing only in the first two symbols — and
   those two are the same two letters in different orders (`TE`, `TO`, `OT`, `TI`,
   `IT`): one ink blot read at different rotations. Seven of the nine words never
   change, and the translation changes completely. A cipher cannot do this.

4. **`tbu/spaceeditcomparison.jpg` shows the same failure more plainly.** Two columns
   labelled "CROATION" and "ENGLISH" contain the *same* pseudo-Latin string; the only
   difference is a moved space. The same block is translated on the left as "They are
   part of the family and they are in the darkest part of the country" and on the right
   as "They have been oppressed by their sincere claims". The author's own README
   explains: *"when you move the space… it changes the entire translation."*

**The quantitative test.** Whatever the script, a letter-level substitution preserves
the distribution of word lengths exactly. Old Church Slavonic has 22.7 % two-letter
words — prepositions, conjunctions, particles. The manuscript has 5.8 %. Their h2 values
are 3.493 and 1.893. The hypothesis is excluded by the data independently of any
reading of the images.

---

## 2. The 2026 "an AI deciphered it" wave

**The claim.** In 2026 several outlets ([Sözcü](https://www.sozcu.com.tr/dunyanin-en-gizemli-kitabinin-sirri-cozuldu-600-yillik-hayalet-dili-okudu-p327785),
[Ege Alternatif](https://www.egealternatif.com/haber/yapay-zeka-basardi-600-yillik-hayalet-dil-cozuldu-voynich-el-yazmasi-nin-sirri-ortaya-cikti_78912/))
reported that an "advanced AI algorithm" had solved the manuscript, identifying a lost
Proto-Romance "ghost language" from the island of Ischia, with the plant drawings as
medicinal collages and the bathing figures as hydrotherapy instructions. A self-published
book (Edward Arthur, April 2026) describes a "historic January 2026 breakthrough" using
an "AlignNet framework".

**Where it comes from.** Not from 2026. The substance is **Gerard Cheshire's 2019
hypothesis** (*Romance Studies*): calligraphic proto-Romance, Dominican nuns, Maria of
Castile, Castello Aragonese on Ischia, c. 1444. The reception at the time:

- **Lisa Fagin Davis** (Medieval Academy of America): *"It's gibberish. The methodology
  falls apart"* — and on the method: start from a theory, hunt Romance dictionaries for a
  matching word, declare the theory proven.
- **Greg Kondrak** (University of Alberta): the proposed letter mappings *"rarely agree
  with each other"*.
- The University of Bristol **withdrew its press release the following day**.

**The quantitative test.** Proto-Romance is a Romance language; its statistics must sit
near Latin, Italian and Spanish:

| | h2 | share of two-letter words |
|---|---|---|
| manuscript | **1.893** | 0.058 |
| Latin | 3.188 | 0.179 |
| Italian | 3.190 | 0.250 |
| Spanish | 3.189 | 0.273 |

A gap of **1.30 bits per character** is not an unrecognised dialect. No academic source
supports the decipherment; peer-reviewed computational work in 2026 states plainly that
the manuscript remains undeciphered.

---

## The common shape

Both claims fail the same way: a method that cannot be wrong. Six readings of one blot;
a translation that changes when a space moves; a dictionary search that terminates when
it succeeds. A method with no failure mode carries no information, whatever the
credentials or the tooling behind it.

The test that distinguishes them is cheap and is in this repository: an identical input
must produce an identical output, and a language hypothesis must survive the
distribution of word lengths.
