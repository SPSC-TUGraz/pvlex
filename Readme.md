
Tool for creating a pronunciation lexicon for Austrian German conversational speech. 

## Installation
Clone repository, change path `cd /path/to/pvlex/`, then `pip install .`.

## Usage 
Create a wordlist with the words that you want to process (one word per line). Change the paths in the configuration file `config.json` and run `pvlex.py`. This creates pronunciation lexicons with multiple pronunciations per word. The pronunciation generation is based on phonetic and phonological rules. Note that a rule-based approach will always produce some unlikely variants as well. Creating Forced Alignments with your data will sort them out and trim your lexicon.

Note: If you want to use your own version of a canonical pronunciation lexicon, you can set the `"RawGermanLexicon"` in the configuration file. Otherwise, you will need an internet connection for accessing the integrated online service to create canonical pronunciations (in this case, please cite [BAS Web Services Grapheme-to-phoneme-conversion tool](https://clarin.phonetik.uni-muenchen.de/BASWebServices/interface/Grapheme2Phoneme) as well). 

If you want to create pronunciation variants with the typical reductions for standard German (as spoken in Germany), set the configuration `ConversationalAustrianGerman` to `false` in the section `GeneralSettings>ruleSets`. 

Example wordlists can be found in `data/wordlists/`, an output lexicon in `data/lexiconLatest_lower.txt`. 

## How to cite 

If you use our code or data in your research, please cite this repository. Use the "Cite this repository" option or:
```
@misc{wepner2025pvlex
	author  = {Wepner, Saskia},
	title   = {pvlex -- Lexicon with Pronunciation Variants for (Austrian) German Conversatinal Speech},
	year    = 2025,
	publisher = {GitHub},
	journal = {GitHub repository},
	howpublished = {\url{https://github.com/SPSC-TUGraz/pvlex}}
}
```
and the article that contains details about some of the general rules used in this code: 
```
@InProceedings{schuppler2014pronunciation,
  author    = {Schuppler, Barbara and Adda-Decker, Martine and Morales-Cordovilla, Juan A},
  booktitle = {Fifteenth Annual Conference of the International Speech Communication Association},
  title     = {Pronunciation variation in read and conversational {Austrian German}},
  year      = {2014},
}
```
