"""
This class implementation is where the actual generation of pronunciation variants (PVs) happens.
It is opposite of dry programming on purpose! Rules cannot be applied all at once as some pronunciation changes depend
on each other (for phonetic/phonological reasons). Therefore, do not change the order in which the functions are
applied. If you want to add more rules, be careful where to put them. (Ask the phonetician of your trust.)
Rules (with examples) are defined in 'config.json'.
"""

import os
import re
from typing import Optional
from pvutils.strip_tags import strip_tags
import inspect  # for debugging
import copy
from collections import OrderedDict
from pvutils.Pronunciation import Pronunciation


# INFO: REGEXSEARCH IF VARIANTS: [\w]*\t(([\w@:]+\s?)*)\t
def move_syllable_stress(lexRaw: dict) -> dict:
    """
    Moves the syllable stress from the vowel to the beginning of the syllable.
    Parameters
    ----------
    lexRaw: dict
        lexicon with stress before vowel (e.g. in syllable centre)
        NAGELKURS: n 'a: . g @ l . k U6 s

    Returns
    -------
    lexNew: dict
        lexicon with stress before syllable
        NAGELKURS: 'n a: . g @ l . k U6 s

    """
    lexNew = {};
    regex = re.compile(r"\'");
    for key, val in lexRaw.items():
        syllables = val.split(r'.');
        newSyls = [];
        for syl in syllables:
            if regex.findall(syl):
                newSyl = re.sub(r"' ?", '', syl.strip());
                newSyl = r"'" + newSyl;
            else:
                newSyl = syl;
            newSyls.append(newSyl.strip());
        newVal = r" . ".join(newSyls)
        newVal = re.sub(r'  ', r' ', newVal)
        lexNew.update({key: newVal});
    return lexNew;


def remove_duplicate_pronunciations(listWduplicates: list) -> list:
    """
        Removes duplicates in a list of pronunciations, i.e.
        e.g.  ["? ' a:", "? ' a:", "? ' O:", "? ' O:"]
          --> ["? ' a:", "? ' O:"]
        while keeping the rules that created these variants (concatenate them)

        It should be called after each function that generate a pronunciation variant.

        Parameters:
            listWduplicates (list): list with duplicates

        Returns:
            listWOduplicates (list): list without duplicates
    """
    listWOduplicates = [];
    if isinstance(listWduplicates, list):
        for pronObj in listWduplicates:
            if pronObj not in listWOduplicates:  # if this pronunciation is not yet in the new list
                listWOduplicates.append(pronObj);
            else:
                idx = listWOduplicates.index(pronObj);
                listWOduplicates[idx].add(pronObj.rules, True);
        return listWOduplicates;


def remove_illegal_neighbourhood(word, listWillegal: list, recentRule: Optional[str]) -> list:
    """
    This function merges neighboured phones that should not be neighboured:
        bräunen     b r OY n  n  --> b r OY n
        eingepackt  aI n g p a k t --> aI n p a k t

    Parameters:
    word          :  str
        for debugging only
    listWillegal  :  list
        list with pronunciations for word

    Returns:
        listWOillegal  :  list

    """
    listWOillegal = [];

    for pronVar in listWillegal:
        # after schwa deletion in ge, merge former g @ syllable with following syllable
        tmpPronVar = pronVar.pron.strip();
        phones = ['b', 'd', 'g', 'p', 't'];
        tmp = tmpPronVar;
        for phone in phones:
            tmpPronVar = re.sub(rf"g \.? {phone}", rf'{phone}', tmpPronVar);

        tmpPronVar = re.sub(r"@ 6", r'E6', tmpPronVar);

        # voiced consonants followed by unvoiced consonants get unvoiced too
        devoicePhones = [('b', 'p'), ('d', 't'), ('g', 'k')];
        for phone in devoicePhones:
            tmpPronVar = re.sub(rf"({phone[0]}) ([ptkSs])", rf'{phone[1]} \2', tmpPronVar);

        # Ngn --> Nn ("Impfungen" is the only affected word so far)
        tmpPronVar = re.sub(r"N \.? g n", r'N n', tmpPronVar);

        # if two similar phones (vowels should be excluded) follow each other in SAME SYLLABLE, always merge them
        mergePhones = ['d', 'g', 'l', 'm', 'n', 't'];
        for phone in mergePhones:
            tmpPronVar = re.sub(rf"([{phone}] ?)+", r"\1", tmpPronVar);

        # mark that an illegal neighbourhood had been removed to avoid confusion
        if tmpPronVar != pronVar.pron:
            pronVar.rules += r"(RIN)"

        # remove syllable, stress and glottal stop symbols and remove illegal neighbourhoods
        if recentRule == 'final_cleanup':
            # remove syllable boundaries and glottat stops
            symbols = [r"\.", "\'", r"\?"];
            if "tmpPronVar" not in locals():  # beautify: I think this will never be true --> remove it
                tmpPronVar = re.sub(r"\. ", r"", pronVar.pron);
            for symbol in symbols:
                tmpPronVar = re.sub(rf"{symbol}", r"", tmpPronVar);

            # remove multiple white spaces
            tmpPronVar = re.sub(r"\s+", r" ", tmpPronVar);

            # split phonemes like 'ts' into their phones beautify: this hard-coding could be moved into config file
            splitPhonemes = {'ts': "t s", 'tS': "t S", 'dZ': "d Z"};
            for phonemeBefore, phonesAfter in splitPhonemes.items():
                tmpPronVar = re.sub(rf"({phonemeBefore})+", rf"{phonesAfter} ", tmpPronVar);

            # remove duplicate phones (for consonants)
            mergePhones = ['b', 'C', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'N', 'p', 'r', 's', 'S', 't', 'v'];
            for phone in mergePhones:
                tmpPronVar = re.sub(rf"([{phone}] ?)+", r"\1", tmpPronVar);

            # change 6 r to 6
            tmpPronVar = re.sub(r"([6]) ?r", r"\1", tmpPronVar);
            # if tmp != tmpPronVar:
            #     print(word + ' ' + tmp + '\t-->\t' + tmpPronVar + '\t' + r'[' + inspect.stack()[0][3] + r']')

        newPronVar = Pronunciation(' '.join(tmpPronVar.split()), pronVar.rules);
        listWOillegal.append(newPronVar);

    listWOillegal = remove_duplicate_pronunciations(listWOillegal);
    return listWOillegal;


class PronVarGenerator():
    """Class for handling multiple pronunciation variants (PVs) for the same word."""
    def __init__(self, lexName, rules):
        self.verboseInfo = True;
        # rules are defined in the configuration file 'config.json'
        self.rules = rules;
        self.ruleCounter = {};
        # initialise count with zero for each rule
        for key, val in self.rules.items():
            self.ruleCounter.update({key: 0});

        self.lexiconName = lexName;  # name for lexicon
        self.lexPath = '';
        self.lexiconRaw = {};  # raw lexicon (what comes out of G2P: 1 word, 1 pronunciation)
        self.lexiconPVs = {};  # lexicon with pronunciation variants
        # self.wordPronType = recordtype("wordPronType", "pronVar ruleSet ruleNames");

    def gen_pron_vars(self, lexiconRaw):
        """
        This method performs deletions/substitutions of phones and adds pronunciation variants
        according to Austrian German Conversational Speech pronunciation rules, as described in

        the suffix "_V" means that this rule adds a variant,
        the suffix "_R" means that this rule replaces the old version

        For details on the rules, please see code descriptions inside the functions. I tried to update all of them and
        added at least one example for faster understanding.

        ADDITIONAL HINTS:
            - Some rules have been extended as they should apply to more cases.
            - Some rules have been added, esp. diphthong rules and things with sonorants.
            - Some rules have been reduced where they shouldn't apply.
        
        Parameters 
        ----------
         lexiconRaw : word list with

        Returns
        -------
        """
        nActiveRules = len(list(filter(lambda elem: elem == True, self.rules.values())));
        nTokens = len(lexiconRaw);
        if self.verboseInfo is True:
            if nActiveRules == 0:
                self.display_verbose_info(self.gen_pron_vars.__name__,
                                          'converting ' + str(nTokens) + ' tokens ');
            else:
                self.display_verbose_info(self.gen_pron_vars.__name__,
                                          'generating pronunciation variants ... '
                                          + 'applying ' + str(nActiveRules) + ' rules to '
                                          + str(nTokens) + ' tokens ');

        self.lexiconRaw = move_syllable_stress(lexiconRaw);

        # iterate through lexicon
        lexiconPVs = dict();
        # pronsWcodes = [];
        for word, word_pron in self.lexiconRaw.items():

            # hierarchisch gleichwertig (--> Reihenfolge egal):
            myProns = [Pronunciation(word_pron, 'canon')];
            myProns = self.finalC_as_k_R(word, myProns);
            myProns = self.medialC_as_k_V(word, myProns);
            myProns = self.voiced2unvoiced_s_R(word, myProns);
            myProns = self.rC2rx_V(word, myProns);
            myProns = self.wordinitial_che_chi2ke_ki_R(word, myProns);
            myProns = self.wordinitial_closed_U_R(word, myProns);
            # : hierarchisch gleichwertig

            # r deletions/substitutions are also input switch rules, so they replace and don't add a variant
            myProns = self.r_deletion_coda_R(word, myProns);
            # myProns = self.r_deletion_coda_R(word, myProns);
            myProns = self.r_substitution_coda_R(word, myProns);
            # myProns = self.r_substitution_beforeconsonant_R(word, myProns);

            # keep this order!!!
            myProns = self.full_vowel_substitution_V(word, myProns);
            myProns = self.vowel_diphthong_exchange_V(word, myProns);
            # ------------------

            # might want to keep this order, as "gecheckt" would be affected like a plosive instead of a sibilant affricate
            myProns = self.ge_deletion_sibilantAffricates_V(word, myProns);
            myProns = self.ge_deletion_plosives_V(word, myProns);
            # ------------------
            myProns = self.schwa_deletion_in_ge_V(word, myProns);

            myProns = self.schwa_deletion_unstressed_closedsyllable_V(word, myProns);
            myProns = self.schwa_deletion_unstressed_opensyllable_V(word, myProns);
            myProns = self.gn2N_V(word, myProns);
            myProns = self.gschwan2N_V(word, myProns);
            myProns = self.Nschwan2N_V(word, myProns);

            myProns = self.t_delition_in_consonantClusters_V(word, myProns);
            myProns = self.t_delition_in_sClusters_V(word, myProns);
            myProns = self.t_deletion_before_plosives_V(word, myProns);
            myProns = self.carryover_assimilation_plosives_V(word, myProns);
            myProns = self.l_vocalisation_V(word, myProns);
            myProns = self.lenition_plosive_V(word, myProns);
            myProns = self.Cx_deletion_coda_V(word, myProns);
            myProns = self.h_deletion_onset_V(word, myProns);

            myProns = self.schwa_deletion_before_n_V(word, myProns);
            myProns = self.nm2m_V(word, myProns);
            # this must be after schwa deletion before n!
            myProns = self.final_n2m_V(word, myProns);
            # these two must be after final n to m, e.g. sieben: s i: b @ n --> s i: b n --> s i: b m --> s i: m
            myProns = self.bilabial_plosive_deletion_afterbefore_m_V(word, myProns);
            myProns = self.alveolar_plosive_deletion_afterbefore_n_V(word, myProns);

            myProns = self.wordfinal_plosive_deletion_V(word, myProns);

            # sicher ist sicher ...
            myProns = remove_illegal_neighbourhood(word, myProns, 'final_cleanup');
            lexiconPVs.update({word: myProns});

        self.lexiconPVs = lexiconPVs;
        self.display_verbose_info(self.gen_pron_vars.__name__,
                                  "generated PV lexicon is stored in member variable self.lexiconPVs")
        return;

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # # # rule-related methods and functions  # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def finalC_as_k_R(self, word: str, pronsWcodes: list) -> list:
        """
        This function replaces GG pronunciation of final 'g' into AG version, e.g.
        fertig: f'E6+tIC  -->  f'E6+tIk
        in GG, this is pronunciated like "ch" in "ich"; in AG, this becomes "k"
    
        Parameters
        ----------
        word : str 
            current word 
        pronsWcodes  :  list of tuples (recordtype)
            list with tuples that contain each
            - pronunciation
            - code for rule set that led to this pronunciation
            - names of rules in rule set that led to this pronunciation
            for word
    
        Returns
        -------
        pronsWcodesClean  :  list
            Like input 'pronsWcodes', but updated if rule applied.
            Possible duplicates in PVs are removed but rule set is kept.

        """
        if not self.rules['finalC_as_k_R']:
            return pronsWcodes;

        if isinstance(pronsWcodes, list):
            # Pronunciation(word_pron, ['canon'])
            # pronsWcodesNew = copy.deepcopy(pronsWcodes);
            pronsWcodesNew = [];
            r1 = re.compile(r'IG$', re.IGNORECASE)
            for myPron in pronsWcodes:
                if r1.search(word):
                    wordPron = re.sub("C$", "k", myPron.pron)
                    myPron.replace(wordPron.strip(), 'finalC_as_k_R');
                    self.ruleCounter['finalC_as_k_R'] += 1;
                pronsWcodesNew.append(myPron);
        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def wordinitial_closed_U_R(self, word: str, pronsWcodes: list) -> list:
        """
        Replace word initial open vowel /u/ with closed vowel if stressed
            Uni:  'U n i:  -->  'u: n i:
        Parameters
        ----------
        word : str
            current word
        pronsWcodes  :  list of tuples (recordtype)
            list with tuples that contain each
            - pronunciation
            - code for rule set that led to this pronunciation
            - names of rules in rule set that led to this pronunciation
            for word

        Returns
        -------
        pronsWcodesClean  :  list
            Like input 'pronsWcodes', but updated if rule applied.
            Possible duplicates in PVs are removed but rule set is kept.

        """
        if not self.rules['wordinitial_closed_U_R']:
            return pronsWcodes;

        if isinstance(pronsWcodes, list):
            # Pronunciation(word_pron, ['canon'])
            # pronsWcodesNew = copy.deepcopy(pronsWcodes);
            pronsWcodesNew = [];
            for myPron in pronsWcodes:
                if word.startswith(('u', 'U')):
                    wordPron = re.sub(r"^(\')(\? ?|\' ?)?U", r"\1\2u:", myPron.pron)
                    if wordPron != myPron.pron:
                        self.ruleCounter['wordinitial_closed_U_R'] += 1;
                        # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");
                    myPron.replace(wordPron.strip(), 'wordinitial_closed_U_R');
                pronsWcodesNew.append(myPron);
        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def wordinitial_che_chi2ke_ki_R(self, word: str, pronsWcodes: list) -> list:
        """
        Converts
            Chemie: C e: m i: --> k e: m i:
        """
        if not self.rules['wordinitial_che_chi2ke_ki_R']:
            return pronsWcodes;

        if isinstance(pronsWcodes, list):
            # Pronunciation(word_pron, ['canon'])
            # pronsWcodesNew = copy.deepcopy(pronsWcodes);
            pronsWcodesNew = [];
            for myPron in pronsWcodes:
                r1 = re.compile(r'^(CHE|CHI)', re.IGNORECASE)
                if r1.search(word):
                    wordPron = re.sub(r"^(\')?C", r"\1k", myPron.pron)
                    myPron.replace(wordPron.strip(), 'wordinitial_che_chi2ke_ki_R');
                    self.ruleCounter['wordinitial_che_chi2ke_ki_R'] += 1;
                pronsWcodesNew.append(myPron);
        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def medialC_as_k_V(self, word: str, pronsWcodes: list) -> list:
        """
        beautify: for words like "eigentlich", we match 'ig' within the word and change 'ich' at its end ...
        This function replaces GG pronunciation of SYLLABLE final 'g' into AG version, e.g.
        dreißigsten: 	d r aI s I C s t @ n  -->  d r aI s I k s t @ n
        in GG, this is pronunciated like "ch" in "ich"; in AG, this becomes "k"
        New pronunciation is added as variant.

        Parameters
        ----------
        word : str
            current word
        pronsWcodes  :  list of tuples (recordtype)
            list with tuples that contain each
            - pronunciation
            - code for rule set that led to this pronunciation
            - names of rules in rule set that led to this pronunciation
            for word

        Returns
        -------
        pronsWcodesClean  :  list
            Like input 'pronsWcodes', but updated if rule applied.
            Possible duplicates in PVs are removed but rule set is kept.

        """
        if not self.rules['medialC_as_k_V']:
            return pronsWcodes;

        if isinstance(pronsWcodes, list):
            # Pronunciation(word_pron, ['canon'])
            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            for wordPron in pronsWcodes:
                r1 = re.compile(r'IG$', re.IGNORECASE)
                r2 = re.compile(r'IG', re.IGNORECASE)
                if not r1.search(word) and r2.search(word):
                    tmpPron = re.sub(" I C", " I k", wordPron.pron)
                    newPron = Pronunciation(tmpPron, wordPron.rules);
                    if newPron != wordPron:
                        newPron.add('medialC_as_k_V');
                        pronsWcodesNew.append(newPron);
                        # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");
                        self.ruleCounter['medialC_as_k_V'] += 1;

        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def voiced2unvoiced_s_R(self, word: str, pronsWcodes: list) -> list:
        """
        This method replaces every voiced s with an unvoiced s
        Vorsicht    fo:6zICt  -->  fo:6sICt
        Ingenieur   InZ@nj2:6  -->  InS@nj2:6
        Dschungel   dZ U N @ l  -->  tS U N @ l

        Parameters
        ----------
        word: str
            current word
        pronsWcodes: list
            list with current variants

        Returns
        -------
        pronsWcodesClean  :  list

        """
        if not self.rules['voiced2unvoiced_s_R']:
            return pronsWcodes;
        # if word.startswith('z'):
        #     print(word)
        if isinstance(pronsWcodes, list):
            pronsWcodesNew = [];
            for myPron in pronsWcodes:
                r1 = re.compile(r'z');
                r2 = re.compile(r'Z');
                r3 = re.compile(r'dZ');
                tmp = re.sub(r3, "tS", myPron.pron);
                tmp = re.sub(r1, "s", tmp);
                tmp = re.sub(r2, "S", tmp);

                if tmp != myPron.pron:
                    self.ruleCounter['voiced2unvoiced_s_R'] += 1;
                    myPron.replace(tmp, 'voiced2unvoiced_s_R');
                pronsWcodesNew.append(myPron);
        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def rC2rx_V(self, word: str, pronsWcodes: list) -> list:
        """
        This function replaces GG pronunciation of "rch" into AG version, e.g.
            Kirche: k'I6rC@  -->  k'I6rx@
        Actually, we don't want to apply this rule for diminutives, such as Bärchen (little bear), but excluding "chen"
        from this rule would skip the plural of Kirche (church) which is Kirchen. So, let's add as variant instead of
        replacing.

        Parameters
        ----------
        word : str
            current word
        pronsWcodes  :  list of tuples (recordtype)
            list with tuples that contain each
            - pronunciation
            - code for rule set that led to this pronunciation
            - names of rules in rule set that led to this pronunciation
            for word

        Returns
        -------
        pronsWcodesClean  :  list
            Like input 'pronsWcodes', but updated if rule applied.
            Possible duplicates in PVs are removed but rule set is kept.
        """
        if not self.rules['rC2rx_V']:
            return pronsWcodes;
        if isinstance(pronsWcodes, list):
            # Pronunciation(word_pron, ['canon'])
            # pronsWcodesNew = copy.deepcopy(pronsWcodes);
            pronsWcodesNew = [];

            # for myPron in pronsWcodes:
            r1 = re.compile(r'RCHEN', re.IGNORECASE);
            r2 = re.compile(r'RCH', re.IGNORECASE);
            if r1.search(word):
                pronsWcodesNew = copy.deepcopy(pronsWcodes);
                for wordPron in pronsWcodes:
                    tmpPron = re.sub(r"6 (\. )?C", r"6 \1x", wordPron.pron)
                    tmpPron = re.sub(r"r (\. )?C", r"r \1x", tmpPron)
                    tmpPron = tmpPron.strip();
                    newPron = Pronunciation(tmpPron, wordPron.rules);
                    if newPron != wordPron:
                        newPron.add('rC2rx_V');
                        pronsWcodesNew.append(newPron);
                        # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");
                        self.ruleCounter['rC2rx_V'] += 1
            if r2.search(word) and not r1.search(word):
                for myPron in pronsWcodes:
                    tmpPron = re.sub("6 (\. )?C", r"6 \1x", myPron.pron);
                    tmpPron = re.sub("r (\. )?C", r"r \1x", tmpPron);
                    # newPron = Pronunciation(tmpPron, wordPron.rules);
                    myPron.replace(tmpPron, 'rC2rx_V');
                self.ruleCounter['rC2rx_V'] += 1;
                pronsWcodesNew.append(myPron);
            pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);

        if not pronsWcodesClean:
            return pronsWcodes;
        return pronsWcodesClean;

    def full_vowel_substitution_V(self, word: str, pronsWcodes: list) -> list:
        """
        Substitute specific set of vowels.
        CAUTION: Do not change order!

        rule a --> O
            ableiten :  'a p l aI t @ n  --> 	'O p l aI t @ n

        rule 'E l --> '9 l
            Kapelle :   k a p 'E l @  -->  k a p '9 l @

        rule O r --> U r (actually, I'd rather change that to o:6)
            korrigieren : k O r i 'g i: r @ n  -->  k U r i 'g i: r @ n
        rule O --> U
            wovon :  v o . 'f O n  -->  v o . 'f U n

        Parameters
        ----------
        word: str
            current word
        pronsWcodes: list
            list with current variants
        Returns
        -------
        pronsWcodesClean : list
            list with new variants
        """
        if not self.rules['full_vowel_substitution_V']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            for wordPron in pronsWcodes:
                # rule O --> U and rule a --> O (A doesn't occur; nonetheless, let's consider it)
                tmpPron = re.sub(r"([aA])(:?) ([^n])(.*)", r"O\2 \3\4",
                                 wordPron.pron);  # for discussion: we might want to change r to 6 here already
                tmpPron = tmpPron.strip();
                # create new instance of 'Pronunciation' in any case, append and count only if something had changed
                newPron = Pronunciation(tmpPron, wordPron.rules);
                if newPron != wordPron:
                    newPron.add('full_vowel_substitution_V_(a->O)');
                    pronsWcodesNew.append(newPron);
                    # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");

                # rule 'E l --> '9 l
                    newPronCopy = newPron;
                    tmpPron = re.sub("'E l", "'9 l", newPronCopy.pron)
                    tmpPron = tmpPron.strip();
                    newPron = Pronunciation(tmpPron, newPron.rules);
                    if newPron != newPronCopy:
                        newPron.add(re.sub(r"(.*)\)", r"\1,El->9l)", newPron.rules));
                        pronsWcodesNew.append(newPron);
                        # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");

                # apply rule on original pronunciation
                tmpPron = re.sub("'E l", "'9 l", wordPron.pron)
                tmpPron = tmpPron.strip();
                newPron = Pronunciation(tmpPron, wordPron.rules);
                if newPron != wordPron:
                    newPron.add('full_vowel_substitution_V_(El->9l)');
                    pronsWcodesNew.append(newPron);
                    # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");

                # rule O r --> U r
                    newPronCopy = newPron;
                    tmpPron = re.sub("'O r", "'U r", newPronCopy.pron)
                    tmpPron = tmpPron.strip();
                    newPron = Pronunciation(tmpPron, newPron.rules);
                    if newPron != newPronCopy:
                        newPron.add(re.sub(r"(.*)\)", r"\1,Or->Ur)", newPron.rules));
                        pronsWcodesNew.append(newPron);
                # apply rule on original pronunciation
                tmpPron = re.sub("O r", r"U r", wordPron.pron);
                tmpPron = tmpPron.strip();
                newPron = Pronunciation(tmpPron, wordPron.rules);
                if newPron != wordPron:
                    newPron.add('full_vowel_substitution_V_(Or->Ur)');
                    pronsWcodesNew.append(newPron);
                    # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");

                # rule O --> U
                    newPronCopy = newPron;
                    tmpPron = re.sub(" (\'?)O ", r" \1U ", newPronCopy.pron)
                    tmpPron = tmpPron.strip();
                    newPron = Pronunciation(tmpPron, newPron.rules);
                    if newPron != newPronCopy:
                        newPron.add(re.sub(r"(.*)\)", r"\1,O->U)", newPron.rules));
                        pronsWcodesNew.append(newPron);
                # apply rule on original pronunciation
                tmpPron = re.sub(r" (\'?)O ", r" \1U ", wordPron.pron);
                tmpPron = tmpPron.strip();
                newPron = Pronunciation(tmpPron, wordPron.rules);
                if newPron != wordPron:
                    newPron.add('full_vowel_substitution_V_(O->U)');
                    pronsWcodesNew.append(newPron);
                    # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");

                if newPron != wordPron:
                    self.ruleCounter['full_vowel_substitution_V'] += 1

        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def vowel_diphthong_exchange_V(self, word: str, pronsWcodes: list) -> list:
        """
        Exchange specific set of vowels/diphthongs.
        CAUTION: Do not change order!!!

        rule aI --> a:
            zwei :      ts v aI  -->  ts v a:

        rule OY --> aI
            Beutel :    b OY t @ l  -->  b aI t @ l

        rule a n --A aU n
            kannst :    k a n s t  -->  k aU n s t

        rule O6 --> U6
            fort:       f O6 t  -->  f U6 t

        rule io --> o in tio (if unstressed "tio" in orthography)
            funktionieren:  f U N k . ts j o . 'n i: . r @ n  -->  f U N k . ts o . 'n i: . r @ n
            HINT: this fails in composite words where there is no secondary stress

        Parameters
        ----------

        Returns
        -------
        pronsWcodesClean : list
            list with new variants
        """
        if not self.rules['vowel_diphthong_exchange_V']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            for wordPron in pronsWcodes:
                # rule a n --> aU n
                tmpPron = re.sub("a n", r"aU n", wordPron.pron);
                tmpPron = tmpPron.strip();
                # create new instance of 'Pronunciation' in any case, append and count only if something had changed
                newPron = Pronunciation(tmpPron, wordPron.rules);
                if newPron != wordPron:
                    newPron.add('vowel_diphthong_exchange_V_an->aUn');
                    pronsWcodesNew.append(newPron);
                    # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");

                # rule aI --> a:
                tmp = newPron  # only for checking whether THIS rule affected the pronunciation
                tmpPron = re.sub("aI", r"a:", newPron.pron);  # sic! should be on possibly changed variant
                tmpPron = tmpPron.strip();
                newPron = Pronunciation(tmpPron, wordPron.rules);
                if newPron != tmp:
                    newPron.add('vowel_diphthong_exchange_V_aI->a:');
                    pronsWcodesNew.append(newPron);
                    # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");

                # rule OY --> aI
                tmp = newPron  # only for checking whether THIS rule affected the pronunciation
                tmpPron = re.sub("OY", r"aI", newPron.pron);  # sic! should be on possibly changed variant
                tmpPron = tmpPron.strip();
                newPron = Pronunciation(tmpPron, wordPron.rules);
                if newPron != tmp:
                    newPron.add('vowel_diphthong_exchange_V_OY->aI');
                    pronsWcodesNew.append(newPron);
                    # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");

                # rule O6 --> U6
                tmpPron = re.sub("O6", r"U6", wordPron.pron);  # sic?
                tmpPron = tmpPron.strip();
                newPron = Pronunciation(tmpPron, wordPron.rules);
                if newPron != wordPron:  # sic! (as soon as this is applied to wordPron. and not to newPron
                    newPron.add('vowel_diphthong_exchange_V_O6->U6');
                    pronsWcodesNew.append(newPron);
                    # print(word + ' :  ' + wordPron.pron + '  ' + newPron.pron + '\t' + r'[' + inspect.stack()[0][3] + r']');

                # rule io --> o in tio
                if re.findall(r"tio", word):
                    tmpPron = re.sub("[^\']ts j o(:)?", r" ts o\1", wordPron.pron);  # sic?
                    tmpPron = tmpPron.strip();
                    newPron = Pronunciation(tmpPron, wordPron.rules);
                    if newPron != wordPron:  # sic! (as soon as this is applied to wordPron. and not to newPron
                        newPron.add('vowel_diphthong_exchange_V_io->o');
                        pronsWcodesNew.append(newPron);
                        # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");

                if newPron != wordPron:
                    self.ruleCounter['vowel_diphthong_exchange_V'] += 1

        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def schwa_deletion_before_n_V(self, word: str, pronsWcodes: list) -> list:
        """
        This function deletes a scha before n.
        sprechen :  S p r E C @ n  -->  S p r E C n

        Parameters
        ----------
        word : str
            current word
        pronsWcodes  :  list of tuples (recordtype)
            list with tuples that contain each
            - pronunciation
            - code for rule set that led to this pronunciation
            - names of rules in rule set that led to this pronunciation
            for word

        Returns
        -------
        pronsWcodesClean  :  list
            Like input 'pronsWcodes', but updated if rule applied.
            Possible duplicates in PVs are removed but rule set is kept.
        """
        if not self.rules['schwa_deletion_before_n_V']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            for wordPron in pronsWcodes:
                tmpPron = re.sub(r"([^Nn]) @ n", r"\1 n", wordPron.pron);
                tmpPron = tmpPron.strip();
                newPron = Pronunciation(tmpPron, wordPron.rules);
                # if word == "sprechen":
                #     print(newPron.pron)
                if newPron != wordPron:
                    newPron.add('schwa_deletion_before_n_V');
                    pronsWcodesNew.append(newPron);
                    # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");
                    self.ruleCounter['schwa_deletion_before_n_V'] += 1

        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def schwa_deletion_in_ge_V(self, word: str, pronsWcodes: list) -> list:
        """
        gemacht: g @ m a x t  -->  g m a x t

        consonant [g] will be devoiced to [k] (in remove_illegal_neighbourhood())
        """

        if not self.rules['schwa_deletion_in_ge_V']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            for wordPron in pronsWcodes:
                tmpPron = re.sub(r"g @ \. ((\')?[fvCjxsShmNlr])", r"k \1", wordPron.pron);
                tmpPron = re.sub(r"k \'(.*)", r"k \1", tmpPron);
                tmpPron = tmpPron.strip();
                newPron = Pronunciation(tmpPron, wordPron.rules);
                if newPron != wordPron:
                    newPron.add('schwa_deletion_in_ge_V');
                    pronsWcodesNew.append(newPron);
                    # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");
                    self.ruleCounter['schwa_deletion_in_ge_V'] += 1

        pronsWcodesNew = remove_illegal_neighbourhood(word, pronsWcodesNew, 'schwa_deletion_in_ge_V');
        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def schwa_deletion_unstressed_opensyllable_V(self, word: str, pronsWcodes: list) -> list:
        """
        This function deletes unstressed schwa's at the end of an open syllable
        Open syllable: Vowel followed by nothing (e.g. 'fly')

        Aufnahmegerät :  aU f . n a: . m @ . g @ . r E: t	-->	aU f . n a: . m . g r E: t
        beautify: I'd like to exclude 'g' as predecessor, check whether that's intended

        Parameters
        ----------
        word : str
            current word
        pronsWcodes  :  list
            list with pronunciations for word

        Returns
        -------
        word_pron_list_new  :  list
        """

        if not self.rules['schwa_deletion_unstressed_opensyllable_V']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            for wordPron in pronsWcodes:
                if re.findall(r'\.', wordPron.pron):  # and re.match("@$", word_pron):
                    tmpPron = []
                    for syllable in wordPron.pron.split(' . '):
                        if "'" in syllable:
                            tmpPron.append(syllable)
                        else:
                            syllable = re.sub(r" @( \. )?$", r"", syllable)
                            tmpPron.append(syllable)
                    tmpPron = " . ".join(tmpPron)
                    # because of joining single syllables, g might remain as the only phone within a syllable => add to next
                    tmpPron = re.sub(r"\. g \.", r". g", tmpPron);

                    tmpPron = tmpPron.strip();
                    newPron = Pronunciation(tmpPron, wordPron.rules);
                    if newPron != wordPron:
                        newPron.add('schwa_deletion_unstressed_opensyllable_V');
                        pronsWcodesNew.append(newPron);
                        # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");
                        self.ruleCounter['schwa_deletion_unstressed_opensyllable_V'] += 1

        pronsWcodesNew = remove_illegal_neighbourhood(word, pronsWcodesNew, 'schwa_deletion_unstressed_opensyllable_V');
        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def schwa_deletion_unstressed_closedsyllable_V(self, word: str, pronsWcodes: list):
        """
        This method only keeps schwa's at the end of an unstressed syllable
        or rather removes schwa's in an unstressed closed syllable.
        Closed syllable: Vowel followed by consonant (e.g. 'hat')

        Gedudel :  g @ . 'd u: . d @ l	-->	 g @ . 'd u: . d l

        Parameters
        ----------
        word : str
            current word
        pronsWcodes  :  list
            list with pronunciations for word

        Returns
        -------
        word_pron_list_new  :  list
        """
        if not self.rules['schwa_deletion_unstressed_closedsyllable_V']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            for wordPron in pronsWcodes:
                if re.findall(r'\.', wordPron.pron):
                    tmpPron = [];
                    for syllable in wordPron.pron.split(' . '):
                        if "'" in syllable:
                            tmpPron.append(syllable);
                        else:
                            syllable = re.sub(r"@ ([^n])", r"\1", syllable);
                            tmpPron.append(syllable);
                    tmpPron = " . ".join(tmpPron);

                    tmpPron = tmpPron.strip();
                    newPron = Pronunciation(tmpPron, wordPron.rules);
                    if newPron != wordPron:
                        newPron.add('schwa_deletion_unstressed_closedsyllable_V');
                        pronsWcodesNew.append(newPron);
                        # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");
                        self.ruleCounter['schwa_deletion_unstressed_closedsyllable_V'] += 1

        pronsWcodesNew = remove_illegal_neighbourhood(word, pronsWcodesNew,
                                                      'schwa_deletion_unstressed_closedsyllable_V');
        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def ge_deletion_plosives_V(self, word: str, pronsWcodes: list) -> list:
        """
        This function removes'g @' at the beginning of a word if
        followed by plosives in the next syllable in the next syllable
        gepolstert:	 g @ p O l s t 6 t -> p O l s t 6 t
        geklaut:	 g @ k l aU t -> k l aU t

        Parameters
        ----------
        word : str
            current word
        pronsWcodes  :  list
            list with pronunciations for word

        Returns
        -------
        pronsWcodesClean  :  list

        """
        if not self.rules['ge_deletion_plosives_V']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            for wordPron in pronsWcodes:
                # only for multiple syllables (we don't want to destroy "gebt" etc.)
                if re.findall(r'\.', wordPron.pron):
                    tmpPron = re.sub(r" ?g @ \.?( \'?[ptbdgk])", r'\1', wordPron.pron);
                    tmpPron = tmpPron.strip();
                    newPron = Pronunciation(tmpPron, wordPron.rules);
                    if newPron != wordPron:
                        newPron.add('ge_deletion_plosives_V');
                        pronsWcodesNew.append(newPron);
                        # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");
                        self.ruleCounter['ge_deletion_plosives_V'] += 1;

        pronsWcodesNew = remove_illegal_neighbourhood(word, pronsWcodesNew, 'ge_deletion_plosives_V');
        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def ge_deletion_sibilantAffricates_V(self, word: str, pronsWcodes: list) -> list:
        """
        This function removes 'g @' at the beginning of a word if
        followed by sibilants in the next syllable
        gecheckt :      g @ tS E k t    -->  tS E k t
        gezahlt :       g @ ts a: l t  -->  ts a: l t

        Parameters
        ----------
        word : str
            current word
        pronsWcodes  :  list
            list with pronunciations for word

        Returns
        -------
        pronsWcodesClean  :  list
        """
        if not self.rules['ge_deletion_sibilantAffricates_V']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            for wordPron in pronsWcodes:
                # only for multiple syllables (we don't want to destroy "gebt" etc.)
                if re.search(r"^'?ge", word) and re.findall(r'\.', wordPron.pron):
                    tmpPron = re.sub(r"^g @ \.?( \'?((ts)|(tS)))", r'\1', wordPron.pron);
                    tmpPron = tmpPron.strip();
                    newPron = Pronunciation(tmpPron, wordPron.rules);
                    if newPron != wordPron:
                        newPron.add('ge_deletion_sibilantAffricates_V');
                        pronsWcodesNew.append(newPron);
                        # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");
                        self.ruleCounter['ge_deletion_sibilantAffricates_V'] += 1

        pronsWcodesNew = remove_illegal_neighbourhood(word, pronsWcodesNew, 'ge_deletion_sibilantAffricates_V');
        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def gn2N_V(self, word: str, pronsWcodes: list):
        """
        beautify: this is one of multiple nasal assimilations. could be merged.
        This function adds variant if orthography contains "gn"

        elektromagnetische: e l E k t r o m a g n e: t I S @	 -> e l E k t r o m a N n e: t I S @

        Parameters
        ----------
        word : str
            current word
        pronsWcodes  :  list
            list with pronunciations for word

        Returns
        -------
        word_pron_list_new  :  list
        """
        if not self.rules['gn2N_V']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            if re.findall('gn', word):
                for wordPron in pronsWcodes:
                    tmpPron = re.sub(r"g n", r'N n', wordPron.pron);
                    tmpPron = re.sub(r"g \. n", r'N n', tmpPron);
                    tmpPron = re.sub(r"k n", r'k N', tmpPron);
                    tmpPron = re.sub(r"k \. n", r'k . N', tmpPron);
                    tmpPron = tmpPron.strip();
                    newPron = Pronunciation(tmpPron, wordPron.rules);
                    if newPron != wordPron:
                        newPron.add('gn2N_V');
                        pronsWcodesNew.append(newPron);
                        # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");
                        self.ruleCounter['gn2N_V'] += 1

        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def gschwan2N_V(self, word: str, pronsWcodes: list):
        """
        beautify: this is one of multiple nasal assimilations. could be merged.
        This function replaces g @ n with N if within one syllable.

        tragen :  t r a: g @ n  -->  't r a: N

        Parameters
        ----------
        word : str
            current word
        pronsWcodes  :  list
            list with pronunciations for word

        Returns
        -------
        word_pron_list_new  :  list
        """
        if not self.rules['gschwan2N_V']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            for wordPron in pronsWcodes:
                tmpPron = re.sub(r"g @ n", r'N', wordPron.pron);
                tmpPron = tmpPron.strip();
                newPron = Pronunciation(tmpPron, wordPron.rules);
                if newPron != wordPron:
                    newPron.add('gschwan2N_V');
                    pronsWcodesNew.append(newPron);
                    # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");
                    self.ruleCounter['gschwan2N_V'] += 1

        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def Nschwan2N_V(self, word: str, pronsWcodes: list):
        """
        beautify: this is one of multiple nasal assimilations. could be merged.
        This function replaces N @ n with N.

        aufgegangen :  'aU f g @ g a N @ n  -->  'aU f g @ g a N

        Parameters
        ----------
        word : str
            current word
        pronsWcodes  :  list
            list with pronunciations for word

        Returns
        -------
        word_pron_list_new  :  list
        """
        if not self.rules['Nschwan2N_V']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            for wordPron in pronsWcodes:
                tmpPron = re.sub(r"N (\. )?@ n", r'N', wordPron.pron);
                tmpPron = tmpPron.strip();
                newPron = Pronunciation(tmpPron, wordPron.rules);
                if newPron != wordPron:
                    newPron.add('Nschwan2N_V');
                    pronsWcodesNew.append(newPron);
                    # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");
                    self.ruleCounter['Nschwan2N_V'] += 1

        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def nm2m_V(self, word: str, pronsWcodes: list):
        """
        beautify: this is one of multiple nasal assimilations. could be merged.
        This function replaces n m with m. Occurs after schwa deletion before n.

        deinem:     d aI n m  -->  d aI m

        Parameters
        ----------
        word : str
            current word
        pronsWcodes  :  list of Pronunciation objects
            list with pronunciations for word and which rules yielded these pronunciations

        Returns
        -------
        pronsWcodesClean  :  list of Pronunciation objects
            with new pronunciations if rule applied to word
        """
        if not self.rules['nm2m_V']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            for wordPron in pronsWcodes:
                # if word == "Datenmengen":
                #     print(wordPron.pron)
                tmpPron = re.sub(r"(.*)(\. )?([^@6] )(\. )?n (\. )?m", r"\1\3\5m", wordPron.pron);
                tmpPron = tmpPron.strip();
                newPron = Pronunciation(tmpPron, wordPron.rules);
                if newPron != wordPron:
                    newPron.add('nm2m_V');
                    pronsWcodesNew.append(newPron);
                    # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");
                    self.ruleCounter['nm2m_V'] += 1

        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def r_deletion_coda_R(self, word: str, pronsWcodes: list) -> list:
        """
        This function deletes r in front of a syllable boundary or the end
        of a word if it is preceeded by A, a, A: or a:
        undurchschaubar	  U n d U6 C S aU b a r --> U n d U6 C S aU b a:
        warten      v a r t @ n  -->  v a: t @ n
        brauchbar	b r aU x b a: r  -->  b r aU x b a:

        Parameters
        ----------
        word : str
            current word
        pronsWcodes  :  list
            list with pronunciations for word

        Returns
        -------
        pronsWcodesClean  :  list
        """
        if not self.rules['r_deletion_coda_R']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            pronsWcodesNew = copy.deepcopy(pronsWcodes);

            for wordPron in pronsWcodes:
                tmpPron = re.sub(r"([Aa]):? r( [pbtdkgfvSZxCGhnml]|( \. (?!('?)('?\?? ?)[aAeEiIoOuU]))|$)", r"\1:\2",
                                 wordPron.pron);
                tmpPron = tmpPron.strip();
                newPron = Pronunciation(tmpPron, wordPron.rules);
                if newPron != wordPron:
                    pronsWcodesNew.remove(wordPron)
                    # make sure to overwrite canonical variant (don't keep both versions)
                    if wordPron.rules == "canon":
                        # pronsWcodesNew.remove(wordPron)
                        newPron.replace(newPron.pron.strip(), 'r_deletion_coda_R');
                    else:
                        # pronsWcodesNew.remove(wordPron)
                        newPron.rules = '|'.join([wordPron.rules, newPron.rules])

                    pronsWcodesNew.append(newPron);
                    # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");
                    self.ruleCounter['r_deletion_coda_R'] += 1

        pronsWcodesNew = remove_illegal_neighbourhood(word, pronsWcodesNew, 'r_deletion_coda_R');
        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def r_substitution_coda_R(self, word: str, pronsWcodes: list) -> list:
        """
            This function substitutes r by 6 if followed by a syllable boundary or
            the end of a word (coda) and preceeded by one of the following vowels
            [EIOYU9eiouy2@]

            Bar :  'b a: r	-->	'b a 6

            Parameters
            ----------
            word : str
                current word
            pronsWcodes  :  list
                list with pronunciations for word

            Returns
            -------
            word_pron_list_new  :  list

        """
        if not self.rules['r_substitution_coda_R']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:

            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            for wordPron in pronsWcodes:
                tmpPron = re.sub(r"([EIOYU9eiouy2@])(:)? r( [pbtdkgfvSZxCGhnml]| \.|$)", r"\1\2 6\3", wordPron.pron);
                tmpPron = tmpPron.strip();
                newPron = Pronunciation(tmpPron, wordPron.rules);
                if newPron != wordPron:
                    pronsWcodesNew.remove(wordPron)
                    # make sure to overwrite canonical variant (don't keep both versions)
                    if wordPron.rules == "canon":
                        # pronsWcodesNew.remove(wordPron)
                        newPron.replace(newPron.pron.strip(), 'r_substitution_coda_R');
                    else:
                        # pronsWcodesNew.remove(wordPron)
                        newPron.rules = '|'.join([wordPron.rules, newPron.rules])
                    pronsWcodesNew.append(newPron);
                    # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");
                    self.ruleCounter['r_substitution_coda_R'] += 1

        pronsWcodesNew = remove_illegal_neighbourhood(word, pronsWcodesNew, 'r_substitution_coda_R');
        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def t_delition_in_sClusters_V(self, word: str, pronsWcodes: list):
        """
        This function deletes the t in st followed by consonants and deletes t in ts preceeded by consonants.

        Festplatte :  f E s t p l a t @	 -->  f E s p l a t @

        Parameters
        ----------
        word : str
            current word
        pronsWcodes  :  list
            list with pronunciations for word

        Returns
        -------
        word_pron_list_new  :  list
        """
        if not self.rules['t_delition_in_sClusters_V']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            for wordPron in pronsWcodes:
                # make s t to s if followed by consonants
                tmpPron = re.sub(r"s t \. ([pbkgfvszSZCGhNmntJlrj])", r's . \1', wordPron.pron);
                tmpPron = re.sub(r"([pbkgfvszSZxGhNmnCJlrtj])( \. )?t ?s", r'\1\2s', tmpPron);
                tmpPron = re.sub(r"(t ?s) t", r'\1', tmpPron);
                tmpPron = tmpPron.strip();
                newPron = Pronunciation(tmpPron, wordPron.rules);
                if newPron != wordPron:
                    newPron.add('t_delition_in_sClusters_V');
                    pronsWcodesNew.append(newPron);
                    # print(word + ' :  ' + wordPron.pron + '\t-->\t' + newPron.pron + '\t' + r'[' + inspect.stack()[0][3] + r']');
                    self.ruleCounter['t_delition_in_sClusters_V'] += 1

        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def t_delition_in_consonantClusters_V(self, word: str, pronsWcodes: list):
        """
        This function deletes 't' in between consonants except plosives.

        dutzendfach: d U t s @ n t f a x  -->  d U t s @ n f a x

        Actually, it is not always recommended to apply that rule after n as in
        Kindheit :  'k I n t . h aI t	 --> 	'k I n . h aI t  =/
        However, sometimes that makes sense, as in
        Veröffentlichung :  f E6 . 9 f . @ n t . l I C . U N  -->  f E6 . 9 f . @ n . l I C . U N
        so we generate that variant.

        Parameters
        ----------
        word : str
            current word
        pronsWcodes  :  list
            list with pronunciations for word

        Returns
        -------
        word_pron_list_new  :  list
        """
        if not self.rules['t_delition_in_consonantClusters_V']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            for wordPron in pronsWcodes:
                tmpPron = re.sub(r"([fvzSsCZxGhNmnJlrj]) t \. ([fvzSsCZxGhNmnJlrj])", r'\1 . \2', wordPron.pron)
                tmpPron = tmpPron.strip();
                newPron = Pronunciation(tmpPron, wordPron.rules);
                if newPron != wordPron:
                    newPron.add('t_delition_in_consonantClusters_V');
                    pronsWcodesNew.append(newPron);
                    self.ruleCounter['t_delition_in_consonantClusters_V'] += 1
                    # print(word + ' :  ' + wordPron.pron + '\t-->\t' + newPron.pron + '\t' + r'[' + inspect.stack()[0][3] + r']');

        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def t_deletion_before_plosives_V(self, word: str, pronsWcodes: list):
        """
        This function deletes t behind vowels if t is followed by plosives.

        Kreditkarte:    k r e d i: t k a r t @  -->  k r e d i: k a r t @
        Stadtpark:      S t a t p a r k  -->  S t a p a r k

        Parameters
        ----------
        word : str
            current word
        pronsWcodes  :  list
            list with pronunciations for word

        Returns
        -------
        word_pron_list_new  :  list
        """
        if not self.rules['t_deletion_before_plosives_V']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            for wordPron in pronsWcodes:
                tmpPron = re.sub(r"([AEIOYU9aeiouy2\@:~]) t \. ([bpkgdt])", r'\1 . \2', wordPron.pron);
                tmpPron = tmpPron.strip();
                newPron = Pronunciation(tmpPron, wordPron.rules);
                if newPron != wordPron:
                    newPron.add('t_deletion_before_plosives_V');
                    pronsWcodesNew.append(newPron);
                    # print(word + ' :  ' + wordPron.pron + '\t-->\t' + newPron.pron + '\t' + r'[' + inspect.stack()[0][3] + r']');
                    self.ruleCounter['t_deletion_before_plosives_V'] += 1

        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def carryover_assimilation_plosives_V(self, word: str, pronsWcodes: list) -> list:
        """
        This function replaces the lenix plosives b, d and g or the stressed
        if preceeded by a syllable boundary and one of these consonant groups ([tk]), ([pk]) or ([tpk])

        Parameters
        ----------
        word : str
            current word
        pronsWcodes  :  list
            list with pronunciations for word

        Returns
        -------
        word_pron_list_new  :  list
        """
        if not self.rules['carryover_assimilation_plosives_V']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            for wordPron in pronsWcodes:
                tmpPron = re.sub(r"(tk) \. b ", r'\1 . p ', wordPron.pron);
                tmpPron = re.sub(r"(pk) \. d ", r'\1 . t ', tmpPron);
                tmpPron = re.sub(r"(tpk) \. g ", r'\1 . k ', tmpPron);
                tmpPron = re.sub(r"(tk) \. 'b ", r"\1 . 'p ", tmpPron);
                tmpPron = re.sub(r"(pk) \. 'd ", r"\1 . 't ", tmpPron);
                tmpPron = re.sub(r"(tpk) \. 'g ", r"\1 . 'k ", tmpPron);
                tmpPron = tmpPron.strip();

                newPron = Pronunciation(tmpPron, wordPron.rules);
                if newPron != wordPron:
                    newPron.add('carryover_assimilation_plosives_V');
                    pronsWcodesNew.append(newPron);
                    # print(word + ' :  ' + wordPron.pron + '\t-->\t' + newPron.pron + '\t' + r'[' + inspect.stack()[0][3] + r']');
                    self.ruleCounter['carryover_assimilation_plosives_V'] += 1

        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def lenition_plosive_V(self, word: str, pronsWcodes: list) -> list:
        """
        beautify
        This function substitutes the plosives t, p and b to d, b and v.

        Arbeit  a: b aI t  -->  a: v aI t

        Parameters
        ----------
        word : str
            current word
        pronsWcodes  :  list
            list with pronunciations for word

        Returns
        -------
        word_pron_list_new  :  list
        """
        if not self.rules['lenition_plosive_V']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            pronsWcodesNew = copy.deepcopy(pronsWcodes);

            for wordPron in pronsWcodes:
                tmpPron = re.sub(r"([AEIOYU9aeiouy2@:~6]) \. b ([AEIOYU9aeiouy2@])", r"\1 . v \2", wordPron.pron);
                tmpPron = re.sub(r"([AEIOYU9aeiouy2@:~6]) \. 'b ([AEIOYU9aeiouy2@])", r"\1 . 'v \2", tmpPron);

                tmpPron = re.sub(r"([AEIOYU9aeiouy2@:~6]) \. t ([AEIOYU96aeiouy2@])", r"\1 . d \2", tmpPron);
                tmpPron = re.sub(r"([AEIOYU9aeiouy2@:~6]) \. 't ([AEIOYU96aeiouy2@])", r"\1 . 'd \2", tmpPron);
                # tmp = tmpPron;
                tmpPron = re.sub(r"([AEIOYU9aeiouy2@:~6]) \. p ([AEIOYU9aeiouy2@])", r"\1 . b \2", tmpPron);
                tmpPron = re.sub(r"([AEIOYU9aeiouy2@:~6]) \. 'p ([AEIOYU9aeiouy2@])", r"\1 . 'b \2", tmpPron);

                tmpPron = tmpPron.strip();
                newPron = Pronunciation(tmpPron, wordPron.rules);
                if newPron != wordPron:
                    newPron.add('lenition_plosive_V');
                    pronsWcodesNew.append(newPron);
                    # print(word + ' :  ' + wordPron.pron + '\t-->\t' + newPron.pron + '\t' + r'[' + inspect.stack()[0][3] + r']');
                    self.ruleCounter['lenition_plosive_V'] += 1

        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def Cx_deletion_coda_V(self, word: str, pronsWcodes: list):
        """
		manner-assimilierung an 'k'
        This function deletes the fricatives x and C if they occur in the coda of a syllable (i.e. after the vowel)
        if it is preceeded by vowels [AEIOYU9aeiouy2@:~]

		beautify: nur wenn danach g oder k kommt

        Wahrscheinlichkeit :  v a: 6 'S aI n l I C k aI t  -->  v a: 6 'S aI n l I k aI t
        Wichtigkeit :  

        Parameters
        ----------
        word : str
            current word
        pronsWcodes  :  list
            list with pronunciations for word

        Returns
        -------
        word_pron_list_new  :  list
        """

        if not self.rules['Cx_deletion_coda_V']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            for wordPron in pronsWcodes:
                tmpPron = re.sub(r"([AEIOYU9aeiouy2@:~]) ([xC])", r"\1", wordPron.pron)
                tmpPron = tmpPron.strip();
                newPron = Pronunciation(tmpPron, wordPron.rules);
                if newPron != wordPron:
                    newPron.add('Cx_deletion_coda_V');
                    pronsWcodesNew.append(newPron);
                    # print(word + ' :  ' + wordPron.pron + '\t-->\t' + newPron.pron + '\t' + r'[' + inspect.stack()[0][3] + r']');
                    self.ruleCounter['Cx_deletion_coda_V'] += 1

        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def final_n2m_V(self, word: str, pronsWcodes: list):
        """
        haben: h a: b n
               -> h a: b m
        Attention: This rule normally only applies if a schwa deletion occured

        Parameters
        ----------
        word : str
            current word
        pronsWcodes  :  list
            list with pronunciations for word

        Returns
        -------
        word_pron_list_new  :  list
        """
        if not self.rules['final_n2m_V']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            for wordPron in pronsWcodes:
                tmpPron = re.sub(r"([bp]) (\. )?n( \.)?", r'\1 \2m', wordPron.pron)
                tmpPron = tmpPron.strip();
                newPron = Pronunciation(tmpPron, wordPron.rules);
                if newPron != wordPron:
                    newPron.add('final_n2m_V');
                    pronsWcodesNew.append(newPron);
                    # print(word + ' :  ' + wordPron.pron + '\t-->\t' + newPron.pron + '\t' + r'[' + inspect.stack()[0][3] + r']');
                    self.ruleCounter['final_n2m_V'] += 1

        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def bilabial_plosive_deletion_afterbefore_m_V(self, word: str, pronsWcodes: list):
        """
        This function deletes bilabial plosives (p,b) after/before m.

        durchkämpft : d U6 C k E m p f t  -->  d U6 C k E m f t
        Klemptner :  'k l E m p t . n 6  'k l E m p . n 6   <--- this is deletion of t, not bilabial plosive
        Impfungen :  '? I m p f U N g @ n  '? I m f U N g @ n

        Parameters
        ----------
        word : str
            current word
        pronsWcodes  :  list
            list with pronunciations for word

        Returns
        -------
        word_pron_list_new  :  list
        """
        if not self.rules['bilabial_plosive_deletion_afterbefore_m_V']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            for wordPron in pronsWcodes:
                tmpPron = re.sub(r"m ([bp]) t", r'm \1', wordPron.pron);  # words like Klemptner --> 'k l E m p . n 6
                tmpPron = re.sub(r"m (\. ?) [p] f", r'm \1 f',
                                 tmpPron);  # look only in other syllable if p followed by f
                tmpPron = re.sub(r"m [bp] ", r'm ', tmpPron);
                tmpPron = re.sub(r"(\. ?)[bp] m", r' m', tmpPron);
                tmpPron = tmpPron.strip();
                newPron = Pronunciation(tmpPron, wordPron.rules);
                if newPron != wordPron:
                    newPron.add('bilabial_plosive_deletion_afterbefore_m_V');
                    pronsWcodesNew.append(newPron);
                    # print(word + ' :  ' + wordPron.pron + '\t-->\t' + newPron.pron + '\t' + r'[' + inspect.stack()[0][3] + r']');
                    self.ruleCounter['bilabial_plosive_deletion_afterbefore_m_V'] += 1

        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def alveolar_plosive_deletion_afterbefore_n_V(self, word: str, pronsWcodes: list):
        """
        This function deletes alveolar plosives (d,t) after/before n.

        angeordnet :  a n g @ O6 d n @ t --> a n g @ O6 n @ t
        öffentlicher :  9 f @ n t l I C 6  -->  9 f @ n l I C 6
        wesentlich :  v e: s @ n t l I C	 -->	v e: s @ n l I C

        Parameters
        ----------
        word : str
            current word
        pronsWcodes  :  list
            list with pronunciations for word

        Returns
        -------
        word_pron_list_new  :  list
        """
        if not self.rules['alveolar_plosive_deletion_afterbefore_n_V']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            for wordPron in pronsWcodes:
                tmpPron = re.sub(r"n [dt] ", r'n ', wordPron.pron);  # only if in same syllable
                tmpPron = re.sub(r"[dt] n( )?", r'n\1', tmpPron);  # only if in same syllable
                tmpPron = tmpPron.strip();
                newPron = Pronunciation(tmpPron, wordPron.rules);

                if newPron != wordPron:
                    newPron.add('alveolar_plosive_deletion_afterbefore_n_V');
                    pronsWcodesNew.append(newPron);
                    # print(word + ' :  ' + wordPron.pron + '\t-->\t' + newPron.pron + '\t' + r'[' + inspect.stack()[0][3] + r']');
                    self.ruleCounter['alveolar_plosive_deletion_afterbefore_n_V'] += 1

        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def l_vocalisation_V(self, word: str, pronsWcodes: list):
        """
        beautify: illegal l vocalisation occurs where stressed vowel is not matched; since it's only adding a variant,
        that's not a problem but still unnecessary

        This method vocalizes "l's" which can be followed by specific consonants
        at a syllable boundary or the end of a word (coda) and which are
        preceeded by specific vocals ("it changes "vocal + l").

        rule uU(:) l --> U I
            Absolventen:  a p . s U l . 'v E n . t @ n  -->  a p . s U I . 'v E n . t @ n

        rule oO(:) l --> OY
            Absolventen:  a p . s O l . 'v E n . t @ n  -->  a p . s OY . 'v E n . t @ n

        rule iI(:) l --> y:
            Silvester :  s I l . 'v E s . t 6  -->  s y: . 'v E s . t 6

        rule @ l --> @
            stapelt: 'S t a: . p @ l t  -->  'S t a: . p @ t

        rule y: l --> y:
            gekühlte :  g @ . 'k y: l . t @  -->  g @ . 'k y: . t @

        rule Y l --> y:
            gültig :  'g Y l . t I k --> 'g y: . t I k

        rule 2: l --> 2:
            Olivenöl :  o . 'l i: . v @ n . 2: l  -->  o . 'l i: . v @ n . 2:

        rule 9 l --> 9:
            Pölten :  'p 9 l . t @ n --> 'p 9: . t @ n


        HINT:   G2P often doesn't output the l in the beginning of a syllable if previous syllable ended with l;
                e.g. for words that have ll in orthography:
                Stelle:  S t E l . @
                That causes l vocalisation where there shouldn't be one. =(
                Maybe we need to correct G2P output like this:
                ll in orthography followed by vowel

        Parameters
        ----------
        word : str
            current word
        pronsWcodes  :  list
            list with pronunciations for word

        Returns
        -------
        word_pron_list_new  :  list
        """
        if not self.rules['l_vocalisation_V']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            for wordPron in pronsWcodes:
                # rule U l --> U I
                tmpPron = re.sub(r"([uU]):? l (\. )([^aeiouyAEIOUY629@])(.*)", r"\1 I \2\3\4", wordPron.pron);

                # rule oO(:) l --> OY
                tmpPron = re.sub(r"(.*)([oO]):? l (\. )([^aeiouyAEIOUY629@])(.*)", r"\1OY \3\4\5", tmpPron);

                # rule iI(:) l --> y: (always long to keep syllable weight)
                # unfortunately, still mdoesn't match stressed vowel behind i l
                # tmp = tmpPron;
                # tmpPron = re.sub(r"(.* )([iI]:? l (\. )(\'?[^aeiouy@jAEIOUY629@])(.*))", r"\1y: \3\4\5", tmpPron);
                tmpPron = re.sub(r"(.* )([iI]:? (\. )?l (\. )?(\'?[^aeiouy@jAEIOUY629@])(.*)?)", r"\1y: \3\4\5\6",
                                 tmpPron)
                tmpPron = re.sub(r"(.* )([iI]:? l$)", r"\1y:", tmpPron);
                # if tmp != tmpPron:
                #     print(word + ' ' + tmp + '  -->  ' + tmpPron)

                # rule 'eE l --> 9
                tmpPron = re.sub(r"[eE] l$", "9:", tmpPron);
                # still doesn't match stressed vowel after e l is replaced;
                tmpPron = re.sub(r"(.*)([eE]):? l (\. )(([^aeiouyAEIOUY629@])(.*))", "\g<1>9: \g<3>\g<4>", tmpPron);

                # rule @ l --> @
                tmpPron = re.sub(r"@ l ([^aeiouyAEIOUY6@92])", r'@ \1', tmpPron);

                # rule y: l --> y:
                tmpPron = re.sub(r"y: l$", "y:", tmpPron);
                tmpPron = re.sub(r"y: l (\. )(([^aeiouyAEIOUY629@])(.*))", r"y: \1\2", tmpPron);

                # rule Y l --> y:
                tmpPron = re.sub(r"Y l$", "y:", tmpPron);
                tmpPron = re.sub(r"Y l (\. )([^aeiouyAEIOUY692@])", r"y: \1\2", tmpPron);

                # rule 2: l --> 2:
                tmpPron = re.sub(r"2: l$", "2:", tmpPron);
                tmpPron = re.sub(r"2: (\. )?l ([^aeiouyAEIOUY692@])", r"2:\1 \2", tmpPron);

                # rule 9 l --> 9:
                tmpPron = re.sub(r"9 l$", "9", tmpPron);
                tmpPron = re.sub(r"9 l (\. )([^aeiouyAEIOUY692@])", r"9: \1\2", tmpPron);

                tmpPron = tmpPron.strip();
                newPron = Pronunciation(tmpPron, wordPron.rules);
                if newPron != wordPron:
                    newPron.add('l_vocalisation_V');
                    pronsWcodesNew.append(newPron);
                    # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");
                    self.ruleCounter['l_vocalisation_V'] += 1
        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    def h_deletion_onset_V(self, word: str, pronsWcodes: list):
        """
        This method deletes a pronounced 'h' in an onset position (word initial).
        Heft: 'h E f t
               -> 'E f t
        Attention: This is a coarticulation rule for realisation between neighbouring words.
        It would not occur for standalone or phrase-inital words.

        Parameters
        ----------
        word : str
            current word
        pronsWcodes  :  list
            list with pronunciations for word

        Returns
        -------
        word_pron_list_new  :  list
        """
        if not self.rules['h_deletion_onset_V']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            # Pronunciation(word_pron, ['canon'])
            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            r1 = re.compile(r'^h', re.IGNORECASE)
            for wordPron in pronsWcodes:
                if r1.search(word):
                    tmpPron = re.sub("^('?)h", r"\1", wordPron.pron)
                    tmpPron = re.sub("' ", r"'", tmpPron)
                    tmpPron = tmpPron.strip();
                    newPron = Pronunciation(tmpPron, wordPron.rules);

                    if newPron != wordPron:
                        newPron.add('h_deletion_onset_V');
                        pronsWcodesNew.append(newPron);
                        # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");
                        self.ruleCounter['h_deletion_onset_V'] += 1;

        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);

        return pronsWcodesClean;

    def wordfinal_plosive_deletion_V(self, word: str, pronsWcodes: list) -> list:
        """
        ... COARTICULATION RULE!!! Only makes sense with a subsequent word, so don't be surprised by some strange PVs.
        """
        if not self.rules['wordfinal_plosive_deletion_V']:
            return pronsWcodes;

        if not isinstance(pronsWcodes, list):
            print('exception handling here')
        else:
            pronsWcodesNew = copy.deepcopy(pronsWcodes);
            for wordPron in pronsWcodes:
                tmpPron = re.sub(r"(\. )?[dtpbkg]$", r'', wordPron.pron);  # remove final plosive
                tmpPron = tmpPron.strip();
                newPron = Pronunciation(tmpPron, wordPron.rules);

                if newPron != wordPron:
                    newPron.add('wordfinal_plosive_deletion_V');
                    pronsWcodesNew.append(newPron);
                    # print(f"{word} :  {wordPron.pron}\t-->\t{newPron.pron}\t[{inspect.stack()[0][3]}]");
                    self.ruleCounter['wordfinal_plosive_deletion_V'] += 1

        pronsWcodesClean = remove_duplicate_pronunciations(pronsWcodesNew);
        return pronsWcodesClean;

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # # # non-rule-related methods and functions  # # # # # # # # # # # # # # # # # # # # # # # # #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def sort_by_keys(self) -> dict:
        """
        This method sorts a pronunciation dictionary by keys (this dictrionary is different in the VIEW from a standard
        Python dict).
        """
        return OrderedDict(sorted(self.lexiconPVs.items()));

    def remove_duplicates_from_lexicon(self, lexWduplicates: dict):
        """ check. (maybe obsolete now, but just to be safe.)
        This method removes duplicates in dictionary values, i.e. in PVs
        e.g.  A : ["? ' a:", "? ' a:", "? ' O:", "? ' O:"]
          --> A : ["? ' a:", "? ' O:"]
        """
        lexWOduplicates = {key: list(set(val)) for key, val in lexWduplicates.items()}
        self.lexiconPVs = lexWOduplicates;
        return lexWOduplicates;

    def cleanup_lexicon(self, lexiconBefore: dict, opts=[]):
        """
        Clean up the lexicon lexicon from syllable boundaries, stress symbols
        or glottal stop symbols. 

        Parameters
        ----------
        lexiconBefore : modified lexicon containing syllable info and glottal stops
        opts : list of string, optional
            Give your options here.
            Possible options are:
            syl    : keep syllable boundaries
            stress : keep stress symbols
            gstop  : keep glottal stop  symbol
            The default is [], which outputs a lexicon without any stress 
            symbols or similar.

        Returns
        -------
        lexiconClean : clean version of lexicon
        """

        # remove duplicates in PVs before cleanup
        lexiconWOduplicates = self.remove_duplicates_from_lexicon(lexiconBefore)
        lexiconClean = {};
        for key, vals in lexiconWOduplicates.items():
            # vals = '\t'.split(val)
            if not opts:
                # default lexicon: no specials
                newvals = [];
                for val in vals:
                    val = re.sub('\?', '', val);
                    val = re.sub('\'', '', val);
                    val = re.sub('\.', '', val);
                    val = strip_tags(val, 'CS')
                    newvals.append(val);

            lexiconClean.update({key: newvals})

        lexiconWOduplicatesClean = self.remove_duplicates_from_lexicon(lexiconClean);
        self.lexiconPVs = lexiconWOduplicatesClean;
        return self.lexiconPVs;

    def write_rule_count(self):
        """
        Export file with counts how often which rule was applied.
        """
        with open(os.path.join(self.lexPath, 'rule_count.txt'), 'w', encoding='utf-8') as f:
            for key, val in self.ruleCounter.items():
                f.write(key + '\t' + str(val) + '\n');
        self.display_verbose_info(self.gen_pron_vars.__name__,
                                  f"Rule count saved to {os.path.join(self.lexPath, 'rule_count.txt')}");
        return;

    def write_lexicon(self, case="", nameExtension=""):
        """
        Export
        """
        if case != '':
            fileName = self.lexiconName + '_' + case;
        else:
            fileName = self.lexiconName;
        with open(os.path.join(self.lexPath, fileName + nameExtension + '.txt'), 'w', encoding='utf-8') as f1, \
                open(os.path.join(self.lexPath, fileName + nameExtension + '__withRules.txt'), 'w', encoding='utf-8') as f2:
            for key, vals in self.lexiconPVs.items():
                for val in vals:
                    pron = val.pron;
                    ruleset = val.rules;
                    if case == 'upper':
                        f1.write(key.upper() + '\t' + pron + '\n');
                        f2.write(key.upper() + '\t' + pron + '\t' + ruleset + '\n');
                    elif case == 'lower':
                        f1.write(key.lower() + '\t' + pron + '\n');
                        f2.write(key.lower() + '\t' + pron + '\t' + ruleset + '\n');
                    else:
                        f1.write(key + '\t' + pron + '\n');
                        f2.write(key + '\t' + pron + '\t' + ruleset + '\n');

        print(f"Lexicons saved to {self.lexPath}\n"
              f"- {fileName + nameExtension}.txt\n"
              f"- {fileName + nameExtension}__withRules.txt");
        return;

    def display_verbose_info(self, funcname, msg):
        if self.verboseInfo:
            print('[%s.%s] %s ...' % (type(self).__name__, funcname, msg))
