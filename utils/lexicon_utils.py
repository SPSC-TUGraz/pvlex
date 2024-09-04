"""
Created on Mon Feb 01 17:33:01 2021
Some useful scripts for handling lexicons for Kaldi.
@author: kia
"""

# import os
# import copy
# from collections import OrderedDict
# from utils.Pronunciation import Pronunciation
from utils.NewPronVarGenerator import *
import inspect
import re
# from utils import *
import pickle
import pandas as pd


def strip_file_extension(string):
    """
    Strip file extension.
    """
    return os.path.splitext(string)[0];

def sort_regular_dict_by_key(unsortedDict) -> None:
    """
    This method sorts a dictionary alphabetically by keys.

    Parameters
    ----------
    unsortedDict : dict
        ... possibly unsorted

    Returns
    -------
    None.
    """

    return dict(OrderedDict(sorted(unsortedDict.items())));

def nested_dict_pairs_iterator(dict_obj):
    """
        This function accepts a nested dictionary as argument
        and iterate over all values of nested dictionaries
        author: https://thispointer.com/python-how-to-iterate-over-nested-dictionary-dict-of-dicts/
    """
    # Iterate over all key-value pairs of dict argument
    for k, v in dict_obj.items():
        if k.startswith('_'):  # skip comments in config file
            continue;
        # Check if value is of dict type
        if isinstance(v, dict):
            # If value is dict then iterate over all its values
            for pair in nested_dict_pairs_iterator(v):
                if k.startswith('_'):  # skip comments in config file
                    continue;
                yield (k, *pair)
        else:
            # If value is not dict type then yield the value
            yield (k, v)

def init_PV_rules(ruleConfiguration, want2genPVs, ruleSets={}):
    """
    read in all rules that could be applied to generate pronunciation variants;
    if "want2genPVs" is False, they are _all_ set False
    """
    rules = {};
    # if certain rule *groups* are switches on/off, individual rule settings are overwritten here
    for keyval in nested_dict_pairs_iterator(ruleSets):
        if bool(keyval[-1]) is False:
            for k in ruleConfiguration[keyval[-2]].keys():
                ruleConfiguration[keyval[-2]].update({k: False})

    # for all rule names, check whether this rule should be applied or not
    for keyval in nested_dict_pairs_iterator(ruleConfiguration):
        if want2genPVs:
            rules.update({keyval[-2]: keyval[-1]});
        else:
            rules.update({keyval[-2]: False});  # set rule to False if want2genPVs is False
    return rules;

def merge_lexicons(lexiconOld: dict, lexiconNew: dict, lexiconNewName: str, lexiconOldName="",
                   sort=True) -> dict:
    """
        This function merges two lexicons, while keeping (key,value)-pairs unique.
        In case, a duplicate key-value pair occurs, the lexicon name where the
        duplicate came from is appended to the rule set names.
        E.g. 'B'
            [Pronunciation: b e: <-- canon]
        --> [Pronunciation: b e: <-- canon, Pronunciation: b <-- brokenWords]
        or  'r'
            [Pronunciation: E r <-- canon, Pronunciation: E 6 <-- canon|r_substitution_syllablefinal_V]
        --> [Pronunciation: E r <-- canon|brokenWords, Pronunciation: E 6 <-- canon|r_substitution_syllablefinal_V]
        or  'R'
            [Pronunciation: E r <-- canon, Pronunciation: E 6 <-- canon|r_substitution_syllablefinal_V]
            [Pronunciation: E r <-- canon, Pronunciation: r <-- brokenWords, Pronunciation: E 6 <-- canon|r_substitution_syllablefinal_V]
        etc.

        NOTE: This was a real brain fuck to implement this. Some additional 'if'-statements seem strange but I think,
              they are needed. Please be careful when trying to condense this code to something more beautiful!

        Parameters
        ----------
        lexiconOld : dict
            ... with (key,value)-pairs that might overlap with lexicon2
        lexiconOldName: str
            name of old lexicon into that lexiconNew is merged
        lexiconNew : dict
            ... with (key,value)-pairs that might overlap with lexicon1
        lexiconNewName: str
            name of lexicon that's merged into lexiconOld
        sort: Optional[bool]
            Set to false, if you don't want to sort by keys after merging.
            Default is True.

        Returns
        -------
        lexiconOut: dict
            ... with all merged but unique entries, sorted by keys
    """
    wordsAlreadySeen = [];
    lenBothLexicons = len(lexiconOld) + len(lexiconNew);
    lexiconOut = dict();
    lexicon1 = copy.deepcopy(lexiconOld);
    if isinstance(lexiconOld, OrderedDict):
        lexiconOld = dict(lexiconOld);
    lexicon2 = copy.deepcopy(lexiconNew);
    if isinstance(lexiconNew, OrderedDict):
        lexiconNew = dict(lexiconNew);
    for key, vals1 in lexicon1.items():
        # if key == "Mikrocontroller":
        #     print(vals1)
        if not isinstance(lexiconOld[key], list):
            vals1 = [vals1];
        lexiconOut.update({key: vals1});  # item into new lexicon
        lexiconOld.pop(key);  # remove that item from lexicon 1
        if key in lexicon2:
            vals2 = lexiconNew[key];
            if not isinstance(lexiconNew[key], list):
                vals2 = [vals2];
            # lexiconOut.update({key: vals1});
            for val2 in vals2:
                if not isinstance(val2, Pronunciation):
                    val2 = Pronunciation(val2, lexiconNewName)

                valsNew = [];
                # we need both values of lexicon1 (old one) and lexiconOut (when there's already a new variant in there)
                # vals = vals1 + lexiconOut[key]
                for val1 in vals1:
                    if not isinstance(val1, Pronunciation):
                        print("Should not see this OR adding lex before PVgerneration: " + key)
                        val1 = Pronunciation(val1, lexiconOldName);
                    if val1 != val2:
                        valsNew.append(val1);
                        # following 'if': for second,...,n-th loop iteration of vals1 while still val2 == vals2[0]
                        if val2 not in valsNew:
                            valsNew.append(val2);
                            # lexiconOut.update({key: valsNew});
                    else:
                        val1.add(f"{val1.rules}[{lexiconNewName}]")
                        if val1 not in valsNew:
                            valsNew.append(val1);
                        else:
                            valsNew[valsNew.index(val1)] = val1;  # overwrite previous entry as it can come from this lexicon only
                        wordsAlreadySeen.append(f"{key}\t{val2.pron}\tcould be removed from "
                                                f"{lexiconNewName}\n");

                # if a value was added in previous loop iteration, we don't want to lose it now, so check whether sth
                # can get lost and prevent
                try:
                    for valOut in lexiconOut[key]:
                        if not isinstance(valOut, Pronunciation):
                            print(f"it's fine, you added the key '{key}' from {lexiconNewName}")
                            valOut = Pronunciation(valOut, lexiconOldName);
                        if valOut not in valsNew:
                            valsNew.append(valOut);
                except KeyError:
                    pass;
                lexiconOut.update({key: valsNew});

            lexicon2.pop(key);  # remove that item from lexicon 2

    # lexicon1 SHOULD be empty now, if not, something went wrong!
    if len(lexiconOld) != 0:
        # print(r'[' + inspect.stack()[7].function + r']' + " Should not see this! Merging lexicons is erroneous.");
        print(r'[merge_lexicons]' + " Should not see this! Merging lexicons is erroneous.");

    # add remaining items to new dict (those that weren't keys of lexicon1)
    lexicon2tmp = copy.deepcopy(lexicon2);
    for key, vals2 in lexicon2tmp.items():
        valsNew = [];
        if not isinstance(lexicon2[key], list):
            vals2 = [vals2];
        for val2 in vals2:
            if not isinstance(val2, Pronunciation):
                val2 = Pronunciation(val2, lexiconNewName);
            if key in lexicon1:
                print(r'[' + inspect.stack()[0][3] + r']' + " Should not see this! Merging lexicons is erroneous.");
            valsNew.append(val2)
            lexiconOut.update({key: valsNew});
        lexicon2.pop(key);  # remove that item from lexicon 2

    # lexicon2 SHOULD be empty now, too. if not, something went wrong!
    if len(lexicon2) != 0:
        print(r'[merge_lexicons]' + " Should not see this! Items left in lexicon after merging!")

    if sort is True:
        sort_regular_dict_by_key(lexiconOut);

    lenMergedLexicon = len(lexiconOut);
    if not lenBothLexicons >= lenMergedLexicon:
        print("CAUTION: Something went wrong while merging:\n",
              f"Length of UNCONDENSED lexicons was {lenBothLexicons}; so length of merged lexicons \n",
              f"must be greater than or equal to {lenBothLexicons}, but is {lenMergedLexicon} instead.\n",
              "That means, you 'generated' additional lexicon entries. Check that!");
    return lexiconOut, wordsAlreadySeen;


def read_lexicon(fName: str, fPath="", fEncoding='utf-8') -> dict:
    """
        This function reads in a dictionary from a textfile of the form
        <key>\t<value>\n
        where <key> is the orthographic representation of a word and <value> its pronunciation.
        One line, one key-value pair.
        Parameters
        ----------
        fName : str
            File name of lexicon that should be read.
        fPath : str
            Path where to find lexicon.
            Default is current working directory.
        fEncoding: Optional[str]
            File encoding.
            Default is 'utf-8'.
        Returns
        -------
        The dictionary.
    """
    lex = dict();
    if not fPath:
        fPath = os.getcwd();
    lines = open(os.path.join(fPath, fName), 'r', encoding=fEncoding).readlines()
    for line in lines:
        if len(line.strip().split(r'{}'.format('\t'))) < 2:
            print(r"Check formatting in lexicon for line:\n");
            print(line)
        [key, newVal] = line.strip().split(r'{}'.format('\t'));

        # if key exists, don't overwrite all variants!
        if key not in lex:
            newVals = [re.sub(r" +", " ", re.sub(r"[\'\.]", r"", newVal)).strip()];
        else:  # if key in lexiconRaw
            oldVals = lex[key]
            if not isinstance(oldVals, list):
                oldVals = [oldVals];
            newVals = copy.deepcopy(oldVals);
            if not isinstance(oldVals, list):
                oldVals = [oldVals];
            if newVal not in newVals:
                newVals.append(re.sub(r" +", " ", re.sub(r"[\'\.]", r"", newVal)).strip());
            else:  # if newVal already in oldVals
                pass

        lex.update({key: list(set(newVals))});
    return lex;


def strip(pronRaw: str) -> str:
    """
    This function strips the symbold for syllable boundaries, syllable stress and glottal stops of a pronunciation string.
    """
    pronStripped = re.sub(r"\?", r"", pronRaw);
    pronStripped = re.sub(r"\'", r"", pronStripped);
    pronStripped = re.sub(r" \. ", r" ", pronStripped);
    return pronStripped;


def write_lexicon(lexicon: dict, fName="", fPath="", case="", fEncoding='utf-8') -> None:
    """
    This method writes two lexicon files:
    - fName.txt: lexicon with lines <key>\t<value>\n (<key> is orthography and <value> pronunciation)
        e.g. drüben	d r y: m
    - fName__withRules.txt: lexicon where each line contains the additional information on which rule led to this
    pronunciation; separator is |, not \t
        e.g. drüben|d r y: m|canon|schwa_deletion_before_n_V|final_n2m_V|bilabial_plosive_deletion_afterbefore_m_V

    Parameters
        ----------
        lexicon : dict
            dictionary with keys = orthographic words and values = their pronunciation of type Pronunciation
        fName : str
            file name of the output lexicon
        fPath : str
            file name of the output lexicon
        case : str
            keep keys case sensitive (default) or make them 'upper' or 'lower' case
        fEncoding: Optional[str]
            File encoding.
            Default is 'utf-8'.
        Returns
        -------
    """
    # also write 'non_silencephones.txt' to annotationtools for all unique phones
    phones = [];
    # rule stuff by xenia ...
    lexicon_dict = {}
    lexicon_data_by_word = {}
    all_rules_by_word = {}
    all_rules = []
    # ... rule stuff by xenia
    if case != '':
        fileName = fName + '_' + case;
    else:
        fileName = fName + "caseSensitive";
    with open(os.path.join(fPath, fileName + '.txt'), 'w', encoding=fEncoding) as f1, \
         open(os.path.join(fPath, fileName + '__withRules.txt'), 'w', encoding=fEncoding) as f2:
        for key, vals in lexicon.items():
            word = key.lower()
            lexicon_data_by_word.update({word: {}})
            if not isinstance(vals, list):
                vals = [vals];
            for val in vals:
                pron = strip(val.pron);
                ruleset = val.rules;
                if case == 'upper':
                    f1.write(key.upper() + '\t' + pron + '\n');
                    f2.write(key.upper() + '|' + pron + '|' + ruleset + '\n');
                elif case == 'lower':
                    f1.write(key.lower() + '\t' + pron + '\n');
                    f2.write(key.lower() + '|' + pron + '|' + ruleset + '\n');
                    # xenia ...
                    pronunciation_dict = {'pron': pron}
                    pronunciation = "".join(pron.split())
                    pronunciation_dict_key = f'{word}_{pronunciation}'
                    rules_of_word = []
                    clustered_rules = []
                    for rule in ruleset.split('|'):
                        symbols = ['+', '->']
                        for s in symbols:
                            while s in rule:
                                rule = '_'.join(rule.split(s, 1))  # change special symbols in rule string to '_'
                        if '&' in rule:
                            for r in rule.split('&'):
                                rules_of_word.append(r.strip())  # split up rules that are united with '&'
                        else:
                            rules_of_word.append(rule)
                        if word == 'ich':  # remove 'ManualDialectExotic' for 'ich' and exchange it with 'Cx_deletion_coda_V' (can be deleted once lexicon is updated)
                            if 'ManualDialectExotic' in rules_of_word:
                                rules_of_word.remove('ManualDialectExotic')
                                rules_of_word.append('Cx_deletion_coda_V')
                                pronunciation_dict['pron'] = 'I'
                                pronunciation_dict_key = f'{word}_I'

                        cluster_rule = rule_clusters(rule)
                        if cluster_rule is not None:
                            clustered_rules.append(cluster_rule)
                    rules_count = count_rules(rules_of_word)
                    if clustered_rules:
                        rules_of_word = rules_of_word + clustered_rules
                    all_rules = list(set(all_rules + rules_of_word))

                    if len(rules_of_word) > 1 and 'canon' in rules_of_word \
                            and 'BrokenWords' not in rules_of_word and 'ForeignWords' not in rules_of_word \
                            and 'ForeignWordsHalbgar' not in rules_of_word:
                        rules_of_word.remove(
                            'canon')  # remove 'canon' from the list if another rule applies for that pronunciation (except for the ones in if-condition)
                    try:
                        rules = all_rules_by_word[word]

                        unique_rules_by_word = list(set(rules + rules_of_word))
                        all_rules_by_word.update({word: unique_rules_by_word})
                    except:
                        all_rules_by_word.update({word: rules_of_word})

                    pronunciation_dict.update({'ruleset': rules_of_word})
                    pronunciation_dict.update({'counted_rules': rules_count})
                    # pronunciation_dict.update({'rules_of_pronunciation': all_rules_by_word[word]})
                    # lexicon_dict.update({pronunciation_dict_key: pronunciation_dict})

                    lexicon_data_by_word[word].update({'all_rules_of_word': all_rules_by_word[word]})
                    lexicon_data_by_word[word].update({pronunciation: pronunciation_dict})
                    # ... xenia
                else:
                    f1.write(key + '\t' + pron + '\n');
                    f2.write(key + '|' + pron + '|' + ruleset + '\n');
                phones.extend(pron.split(' '));
        # xenia ...
        lexicon_data_by_word['all_rules_in_lexicon'] = all_rules
        # with open('csv_filename.csv', 'a') as f:
        #     csv_matrix.to_csv(f, header=f.tell() == 0, index=False)
        # save data structure into file
        with open(f'{fPath}/lexicon_dict_{fileName}_lexicon_data_by_word.npy', 'wb') as f:
            pickle.dump(lexicon_data_by_word, f)
        # ... xenia
    print('Lexicon saved to %s as \'%s.txt\'' % (fPath, fileName));
    print('Lexicon with rules saved to %s as \'%s\'' % (fPath, fileName + '__withRules.txt'));
    with open(f"{fPath}/nonsilence_phones.txt", 'w',
              encoding='utf-8') as fPhone:
        for phone in sorted(set(phones)):
            if phone == '':
                continue;
            fPhone.write(f"{phone}\n");
    if case == "lower" or case == "upper":
        with open(os.path.join(fPath, fileName + '.txt'), 'r', encoding=fEncoding) as f1:
            lines = f1.readlines();
        uniqueLines = sorted(list(set(lines)));
        with open(os.path.join(fPath, fileName + '.txt'), 'w', encoding=fEncoding) as f1:
            for line in uniqueLines:
                f1.write(line);

    return;


def write_wordlist(lexicon: dict, fName="", fPath="",
                   fEncoding='utf-8') -> None:
    """
    Write a word list for all word tokens in a lexicon. One word token per line.
    """
    with open(f"{fPath}/wordlist_{fName}.txt", 'w', encoding=fEncoding) as f:
        for key in lexicon.keys():
            f.write(f"{key}\n");
    return;

def rule_clusters(rule):
    """ by xenia """
    plosive_deletions = ['alveolar_plosive_deletion_afterbefore_n_V', 'bilabial_plosive_deletion_afterbefore_m_V',
                         't_deletion_before_plosives_V', 't_delition_in_consonantClusters_V',
                         't_delition_in_sClusters_V',
                         'wordfinal_plosive_deletion_V']
    vowel_substitutions = ['full_vowel_substitution_V_El_9l' 'full_vowel_substitution_V_O_U',
                           'vowel_diphthong_exchange_V_O6_U6', 'vowel_diphthong_exchange_V_OY_aI']
    vowel_diphthongation = ['full_vowel_substitution_V_O_U_a_O', 'vowel_diphthong_exchange_V_an_aUn']
    vowel_monophthongation = ['vowel_diphthong_exchange_V_aI_a:', 'vowel_diphthong_exchange_V_io_o']
    r_reduction = ['r_deletion_coda_R', 'r_substitution_coda_R']
    schwa_deletion = ['schwa_deletion_before_n_V', 'schwa_deletion_in_ge_V',
                      'schwa_deletion_unstressed_closedsyllable_V', 'schwa_deletion_unstressed_opensyllable_V']

    result = None
    if rule in plosive_deletions:
        result = 'plosive_deletions'
    elif rule in vowel_substitutions:
        result = 'vowel_substitutions'
    elif rule in vowel_diphthongation:
        result = 'vowel_diphthongation'
    elif rule in vowel_monophthongation:
        result = 'vowel_monophthongation'
    elif rule in r_reduction:
        result = 'r_reduction'
    elif rule in schwa_deletion:
        result = 'schwa_deletion'
    return result

def postprocess_g2p(g2pout: str, fPath, inputLexName) -> dict:
    """
    Convert g2p output to Python dict and save to file.
    """
    g2pOutputCrazy = g2pout.split('\n');
    lexiconRaw = {};
    for pair in g2pOutputCrazy:
        if pair.strip() != "":
            try:
                lexiconRaw.update({pair.split(';')[0]: pair.split(';')[1]})
            except IndexError:
                print(f"skipping invalid line in g2p output:\n{pair}")
    # save raw g2p output to file
    df = pd.DataFrame.from_dict(lexiconRaw, orient="index")
    df.sort_index(inplace=True)
    df.to_csv(f"{fPath}/{strip_file_extension(inputLexName)}_g2pout.txt", sep='\t', header=False);
    print(f"saved original g2p output to \n{fPath}/{strip_file_extension(inputLexName)}_g2pout.txt")
    return lexiconRaw;

def check_and_prepare_wordlist(fPath: str, wlName: str) -> int:
    """
    Check whether the word list exists, and remove potential duplicate words. Return number of words in the word list.
    """
    try:
        with open('/'.join([fPath, wlName]), 'r', encoding='utf-8') as wl:
            wordList = wl.readlines()
            wordListNew = list(set(wordList))
            if len(wordListNew) != len(wordList):
                with open('/'.join([fPath, wlName + ".bckp"]), 'w', encoding='utf-8') as bckp:
                    bckp.writelines(sorted(wordList))
                with open('/'.join([fPath, wlName]), 'w', encoding='utf-8') as wl_no_duplicates:
                    wl_no_duplicates.writelines(sorted(wordListNew))
    except FileNotFoundError:
        raise FileNotFoundError(f"Could not find German wordlist (file {wlName}) in {fPath}.\n"
                                f"There's nothing I can do for you.")
    return len(wordListNew);

def overwrite_pronunciations(config, fPath, lex):
    """
    Overwrite specific pronunciations (as defined in the special lexicons).
    Why?
    - Non-existing-on-the-fly-created words (often Denglish) might have a wrong pronunciation.
    - There are a couple of systematic errors in the g2p output.
    """
    for lexName in config["GeneralSettings"]["overwritePronunciations"]["LexNames"].keys():
        if config["GeneralSettings"]["overwritePronunciations"]["LexNames"][lexName]["want2do"] is True:
            fNameManCorr = config["GeneralSettings"]["overwritePronunciations"]["LexNames"][lexName]["lexName"]
            try:
                correctedLines = open(os.path.join(fPath, fNameManCorr), 'r',
                                      encoding='utf-8').read().splitlines();
                corrLines = {};
                for lin in correctedLines:
                    corrLines.update({lin.split('\t')[0]: lin.split('\t')[1]})
                for key, val in lex.items():
                    if key in corrLines:
                        lex.update({key: corrLines[key]});
            except FileNotFoundError:
                print(f"You wanted to {lexName} pronunciation with manual corrections but no file with\n"
                      f"these corrections could be found ({fNameManCorr}).\nI'll discard that step.")
    return lex;

def grasslang2g2plang(g2plangs: dict, lang: str) -> str:
    """
    Convert name of language code to its g2p representation.
    """
        # {"DE": "deu",
        #         "DG": "deu",
        #         "EN": "eng",
        #         "HR": "hun",
        #         "FR": "fra-FR",
        #         "IT": "ita",
        #         "JA": "jpn-JP",
        #         "PT": "spa-ES",
        #         "ES": "spa-ES",
        #         "SV": "swe-SE",
        #         "L": "deu",
        #         "DI": "deu",
        #         "DEN": "deu",
        #         }
    return g2plangs[lang];

def count_rules(rules):
    """ by xenia """
    deletions = ['deletion', 'delition']
    deletion_count = 0
    rules_to_remove = ['canon', 'BrokenWords', 'ForeignWords', 'ForeignWordsHalbgar', 'MultiWordExpressions',
                       'SpellingAlphabet', None]
    cleaned_rules = [rule for rule in rules if rule not in rules_to_remove]
    for d in deletions:
        for r in cleaned_rules:
            if d in r:
                deletion_count += 1

    substitution_count = len(cleaned_rules) - deletion_count

    return {'#deletions': deletion_count, '#substitutions': substitution_count}

def write_homophone_lexicon(lexicon: dict, fName: str, fPath="", fEncoding='utf-8', nameExtension="") -> None:
    """
        This method writes two homophone lexicon files with a count that shows how many words are pronounced like this.
        - fName_homophones.txt One line looks like this:
            <pronunciation>\t<count>\t<ORTHOGRAPHY-1>\t...\t<ORTHOGRAPHY-n>
        e.g.
            a:	7	A	a	ah	ai	auch    à
        - fName_homophones__withRules.txt One line looks like this:
            <pronunciation>\t<count>\t<ORTHOGRAPHY-1>\t[<rules-yielding-this-pronunciation>]\t...\t<ORTHOGRAPHY-n> [<rules-yielding-this-pronunciation>]
        e.g.
            a:  7   A [canon|spell]	a [canon]   ah [canon]	ai [canon|vowel_diphton_exchange_V_aI->a:]	auch [dialect]	à [canon]

        Parameters
        ----------
        lexicon: dict
            The lexicon.
        fName: str
            file name of the lexicon, '_homophones' is appended
        fPath: Optional[str]
            file path, default is os.getcwd()
        fEncoding: Optional[str]
            file encoding; default is utf-8
    """
    fileName = fName + nameExtension + '_homophones';
    with open(os.path.join(fPath, fileName + '.txt'), 'w', encoding=fEncoding) as f1, \
            open(os.path.join(fPath, fileName + '__withRules.txt'), 'w', encoding=fEncoding) as f2:
        for key, vals in lexicon.items():
            if not isinstance(vals, list):
                vals = [vals];
            valsAndRules = [];
            allVals = [];
            for val in vals:
                valsAndRules.append(val.pron + r' [' + val.rules + r']');
                allVals.append(val.pron);
            f1.write(key + '\t' + str(len(allVals)) + '\t' + '\t'.join(allVals) + '\n');
            f2.write(key + '\t' + str(len(allVals)) + '\t' + '\t'.join(valsAndRules) + '\n');

    print(f"Lexicons saved to {fPath}\n"
          f"- {fileName}.txt\n"
          f"- {fileName}__withRules.txt");
    return;


def remove_duplicates(lexicon: dict, case="") -> dict:
    """
        2do: needs to be revised. Currently not needed as apparently no duplicates are produced by my code.
             However, we could need that one day.
        This method removes duplicates from a lexicon. Duplicates may occur when making keys uppercase.

        Parameters
        ----------
        lexicon: dict
            The lexicon.
        case: Optional[str]
            'upper' or 'lower' for making keys uppercase or lowercase.
            Default is '' (keep case).
        Returns
        -------
        The lexicon.
    """
    lex = dict();
    if case == 'upper' or case == 'lower':
        lexicon = make_case(lexicon, case);
    for key, vals in lexicon.items():
        if isinstance(vals, list):
            vals = list(set(vals));  # makes unique
        else:
            vals = [vals];
        lex.update({key: vals});
    return lex;


def make_case(lexicon: dict, case: str):
    """
        This function makes keys uppercase or lowercase.

        Parameters
        ----------
        lexicon: dict
            The lexicon.
        case: Optional[str]
            'upper' or 'lower' for making keys uppercase or lowercase.
        Returns
        -------
        None.
    """
    lex = dict();
    for key, vals in lexicon.items():
        if case == 'upper':
            newKey = key.upper();
        elif case == 'lower':
            newKey = key.lower();
        else:
            raise KeyError('case %s is not allowed, use "upper" or "lower"');

        if not isinstance(vals, list):
            vals = [vals];
        if newKey not in lex:
            lex.update({newKey: vals});
        else:
            for val in vals:
                if val not in lex[newKey]:
                    lex[newKey].append(val);

    return lex;


def sort_dict_by_pronunciations(lexicon: dict) -> dict:
    """
    This function sorts a dictionary by keys and returns it.
    Parameters
    ----------
    lexicon: dict
        The lexicon to be sorted
    Returns
    -------
    the sorted lexicon
    """
    # convert to Pronunciation data type if not already
    lexTmp = dict();
    for key, vals in lexicon.items():
        if not isinstance(vals, list):
            vals = [vals];
        newVals = [];
        for val in vals:
            if not isinstance(val, Pronunciation):
                val = Pronunciation(val, 'given');
            newVals.append(val)

        lexTmp.update({key: newVals});

    reverseLexicon = dict();

    for key, vals in lexTmp.items():
        for val in vals:
            if val.pron not in reverseLexicon:
                newPron = Pronunciation(key, val.rules);
                allProns = [newPron];
            else:
                # print(key + '  ' + val.pron + '  ' + val.rules);
                allProns = reverseLexicon[val.pron]
                if not isinstance(allProns, list):
                    allProns = [allProns];
                newPron = Pronunciation(key, val.rules);
                allProns.append(newPron);
            reverseLexicon.update({val.pron: allProns});

    return reverseLexicon;


def get_homophones(lexicon: dict) -> dict:
    """
    This function returns a dictionary containing all homophones, sorted by pronunciations:
    key is pronunciation, values are all orthographic words
    Note: Contains only the homophones, i.e. multiple words with the same pronunciation. That means that many words
    (those with unique pronunciation) are NOT part of the returned lexicon!
    """

    reverseLexicon = sort_dict_by_pronunciations(lexicon);
    lexiconHomophone = dict();
    for key, vals in reverseLexicon.items():
        if len(vals) > 1:
            lexiconHomophone.update({key: vals});
    sort_regular_dict_by_key(lexiconHomophone);
    return lexiconHomophone;


def convert2austrianPhones(lexicon: dict, isPronLex=False) -> dict:
    """
    This function replaces all foreign phones that are unlikely to occur with Austrian speakers with more natural
    phones.
    isPronLex: pronunciation lexicon has different data types (consists of variables of class 'Pronunciation'); so we're
    no able to access the phone sequence as the value of a Python dictionary, but as Pronunciation.pron
    """
    lexiconNew = {};
    for key, vals in lexicon.items():
        newVals = [];
        if not vals and key == "Mochi":
            vals = ["m o: tS I"]
        for val in vals:
            if isPronLex:
                valOld = val;
                val = val.pron;
            valNew = re.sub("z", "s", val);
            valNew = re.sub("dZ", "tS", valNew);
            valNew = re.sub("dS", "tS", valNew);
            valNew = re.sub("Z", "S", valNew);
            valNew = re.sub(r"\{", "E", valNew);
            valNew = re.sub("B", "b", valNew)
            valNew = re.sub("G", "g", valNew)
            valNew = re.sub("D", "d", valNew)
            valNew = re.sub("T", "ts", valNew)
            valNew = re.sub("V", "a", valNew)
            valNew = re.sub("A", "a", valNew)
            valNew = re.sub("H", "u", valNew)  # French [u]
            valNew = re.sub("Q", "O", valNew)  # from English
            valNew = re.sub("e@", "E:6", valNew)
            valNew = re.sub("rr", "r", valNew)
            valNew = re.sub("pp", "p", valNew)  # Italian 'pp'
            valNew = re.sub("ll", "j", valNew)  # Spanish 'll' to German [j]
            valNew = re.sub(r"r\\", "r", valNew)
            valNew = re.sub("@U", "oU", valNew)
            valNew = re.sub("I@", "i:", valNew)  # English 'e' in 'hero'
            valNew = re.sub("a~", "O", valNew)
            valNew = re.sub("ttS", "tS", valNew)
            valNew = re.sub("o~", "O", valNew)
            valNew = re.sub("e~", "@", valNew)
            valNew = re.sub("OI", "OY", valNew)
            newPron = valNew;
            if isPronLex is True:
                newPron = Pronunciation(valNew, valOld.rules);
            newVals.append(newPron);
        if isPronLex is True:
            listWOduplicates = remove_duplicate_pronunciations(newVals)
        else:
            listWOduplicates = newVals;
        lexiconNew.update({key: listWOduplicates});

    return lexiconNew;


def long2shortVowels(lexicon: dict) -> dict:
    """
    This function converts all long vowels, such as [a:] to short vowels [a].
    Duplicate entries that occur will be removed immediately.
    """
    lexiconNew = {};
    for key, vals in lexicon.items():
        newVals = [];
        if not isinstance(vals, list):
            vals = [vals];
        for val in vals:
            valNew = re.sub(":", "", val.pron);
            newPron = Pronunciation(valNew, val.rules);
            newVals.append(newPron);
        listWOduplicates = remove_duplicate_pronunciations(newVals)
        lexiconNew.update({key: listWOduplicates});

    return lexiconNew;


def reduce_phone_set(lexicon: dict, mergePhones: dict) -> dict:
    """
        This function merges phones that are barely distinguished in (Austrian) German.
        Duplicate entries that occur will be removed immediately.
        2do: it makes much more sense to do this minimisation before generation of PVs
    """
    lexiconNew = {};
    rekeks = rf"({'|'.join([str(phn) for phn in mergePhones.keys()])})"
    for key, vals in lexicon.items():
        newVals = [];
        if not isinstance(vals, list):
            vals = [vals];
        for val in vals:
            if re.findall(re.compile(rekeks), val.pron):
                valNew = val.pron
                for phone in mergePhones.keys():
                    valNew = re.sub(f"{str(phone)}", f"{mergePhones[str(phone)]}", valNew);
                newPron = Pronunciation(valNew, val.rules);
                newVals.append(newPron);
            else:
                newVals.append(val)
        listWOduplicates = remove_duplicate_pronunciations(newVals)
        lexiconNew.update({key: listWOduplicates});

    return lexiconNew;