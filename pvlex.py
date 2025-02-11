import sys
# import os
import json5 as json
# import numpy as np
# from pvutils.NewPronVarGenerator import PronVarGenerator
from g2p import g2p
# import pandas as pd
from pvutils.pvutils import *
import re


def generate_PV_lexicon(inputLexName, fPath, config={}, wantPVs=True) -> (dict, str):
    """
    Take (GRASS) wordlist and create pronunciation lexicon with:
    - canonical pronunciations
    and optionally:
    - pronunciation variants (PVs),
    - appending additional lexicons,
    - reduce phone set
    ... as defined in the config file.
    """

    # log file to track duplicate words (could be thrown out of additional lexicons if needed)
    logFile = open(f"{fPath}/PVGenerationAndWordsAlreadySeen.log", 'w', encoding='utf-8');
    # path for wordlists
    wlPath = '/'.join([fPath, "wordlists"])

    # try to read in configuration if not gives as parameter
    if not config:
        try:
            # genpath = "pvlexicon/code"; @Julian: ggf. diese Zeile wieder reinnehmen
            genpath = sys.path[-1]
            configname = "config.json";
            # print(genpath)
            if fPath == "":
                fPath = '/'.join([os.path.dirname(sys.path[-1]), "data"]);
            with open('/'.join([genpath, configname]), 'r') as file:
                # cfg = yaml.safe_load(file);
                config = json.load(file);
        except FileNotFoundError:
            raise FileNotFoundError("you must provide a configuration file\n"
                                    f"I tried to open {'/'.join([genpath, configname])}");

    want2genPVs = config["GeneralSettings"]["want2GenPVs"];

    # read in raw lexicon, if any
    if config["GeneralSettings"]["updateLexicon"] is False:
        try:
            lines = open('/'.join([fPath, inputLexName]), 'r', encoding='utf-8').readlines()
            lexiconRaw = {};
            for line in lines:
                [key, val] = line.strip().split(r'{}'.format('\t'));
                lexiconRaw.update({key: val});
            inputLexName = strip_file_extension(inputLexName)
        except FileNotFoundError:
            print(f"[WARNING] Could not find raw lexicon (file {inputLexName}) in {fPath}.\n"
                  f"I'll create it from your wordlist.")

    else:
        # no lexicon found or should be updated, load wordlist and send to g2p for getting canonical pronunciations
        wordlistNames = config["WordListNames"].split(' ')
        wlPath = '/'.join([fPath, "wordlists"])
        nWords = check_and_prepare_wordlist(wlPath, wlNames=wordlistNames)

        # get canonical pronunciations from grapheme-to-phoneme (g2p) conversion tool
        mainLanguage = grasslang2g2plang(config["GeneralSettings"]["PronunciationSettings"]["LanguageTagsG2P"],
                                         config["MainLanguage"])
        parser = g2p.parser;
        g2pOutput = ""
        print(f"... using g2p for {mainLanguage} ({nWords} words) ...")
        for wordlistName in wordlistNames:
            print(os.path.join(config["BasePath"], wordlistName))
            args = parser.parse_args([os.path.join(wlPath, wordlistName), '--iform=txt', '--oform=tab',
                                      '--stress=yes', '--syl=yes', f"--lng={mainLanguage}"])
            g2pOutput += g2p.process(args);
        # postprocess raw g2p output
        lexiconRaw = postprocess_g2p(g2pOutput, fPath, inputLexName);

    # overwrite some wrong g2p pronunciations
    if config["GeneralSettings"]["overwritePronunciations"]["want2do"] is True:
        loadPath = '/'.join([fPath, "SpecialLexicons"]);
        lexiconRaw = overwrite_pronunciations(config=config, fPath=loadPath, lex=lexiconRaw)

    # initialise which rules should be applied, if any; see config file
    ruleSets = config["GeneralSettings"]["ruleSets"]
    rules = init_PV_rules(config['PronunciationVariation'], want2genPVs, ruleSets);

    # initialise PV generator
    PVGen = PronVarGenerator(lexName=strip_file_extension(config["OriginalLexiconName"]), rules=rules);
    lexPath = '/'.join([fPath, "intermediatelexicons"])
    PVGen.lexPath = lexPath;

    # generate pronunciation variants
    PVGen.gen_pron_vars(lexiconRaw);
    PVGen.write_rule_count();
    PVGen.lexiconPVs = PVGen.sort_by_keys()
    # PVGen.lexiconPVs = PVGen.remove_duplicates_from_lexicon(PVGen.lexiconPVs);

    # create a fesh copy of the current lexicon, then add others
    lexiconNew = copy.deepcopy(PVGen.lexiconPVs);
    write_lexicon(lexiconNew, f"{PVGen.lexiconName}_", lexPath, case="lower")
    lexHomophonesOnly = get_homophones(lexiconNew);
    write_homophone_lexicon(lexHomophonesOnly, PVGen.lexiconName, lexPath);

    # append manual lexicons
    for key, val in config["SpecialLexicons"]["Lexicons"].items():
        # check whether variable is set true to append current special lexicon
        if val["want2add"] is True:
            fname = val["lexName"];
            try:
                lexName = re.sub(r"__(.*).txt", r"\1", fname);
                lex = read_lexicon(fname, loadPath);
                # convert phones of foreign language to their Austrian corresponding pronunciation
                if key in ["addForeignWords", "addForeignWordsHalbgar"]:
                    lexTmp = convert2austrianPhones(lex);
                else:
                    lexTmp = lex;
                lexiconNew, logInfo = merge_lexicons(lexiconNew, lexTmp, lexName);
                if logInfo is not []:
                    logFile.writelines(logInfo);
            except FileNotFoundError:
                print(f"CAUTION: you wanted to {key} but I couldn't find the required file\n"
                      f"{os.path.join(loadPath, fname)}");

    # [optional] convert all long vowels to short vowels; if that produces duplicates in the pronunciation, they are thrown
    if config["GeneralSettings"]["convertLong2ShortVowels"] is True:
        lexiconNew = long2shortVowels(lexiconNew);
        lexiconNew = convert2austrianPhones(lexiconNew, isPronLex=True);

    # [optional] minimise the phone set
    if config["GeneralSettings"]["reducePhoneSet"] is True:
        phonesToBeMerged = {}
        for key in config["GeneralSettings"]["PhoneSetMinimisation"]:
            if key.startswith('_'):  # skip comments in config file
                continue;
            phonesToBeMerged.update({str(key): str(config["GeneralSettings"]["PhoneSetMinimisation"][key])});
        lexiconNew = reduce_phone_set(lexiconNew, phonesToBeMerged);

    # sort dict alphabetically before writing to file
    sort_regular_dict_by_key(lexiconNew);
    # write to file
    lexName = strip_file_extension(config["FinalLexiconName"]);
    write_lexicon(lexiconNew, lexName, fPath, case="lower")
    write_wordlist_(lexiconNew, lexName, wlPath)

    # write homophone lexicon to file
    lexHomophonesOnly = get_homophones(lexiconNew);
    write_homophone_lexicon(lexHomophonesOnly, 'lexiconLatest', lexPath);

    logFile.close();

    # write nonsilence phones
    with open(f"{fPath}/nonsilence_phones.txt", 'w') as f:
        allProns = ""
        for prons in lexiconNew.values():
            for pron in prons:
                allProns += pron.pron + ' '
        phones = list(set(allProns.split(' ')))
        try:
            phones.remove(' ')
        except ValueError:
            pass;
        for phone in sorted(phones):
            if phone != ' ':
                f.write(phone + '\n')

    return lexiconNew, lexName;


if __name__ == "__main__":

    if len(sys.argv) < 4:
        configfname = "config.json";
        fpath = os.path.join(os.path.dirname(os.getcwd()), 'data');
    else:
        configfname = sys.argv[1];
        inputlexname = sys.argv[2];
        fpath = os.path.join(os.path.dirname(os.getcwd()), sys.argv[3]);
        print(fpath)
    try:
        with open(configfname, 'r') as file:
            cfg = json.load(file);
        inputlexname = cfg["RawGermanLexicon"];
    except FileNotFoundError:
        raise FileNotFoundError(f"cannot find your configuration file 'config.json'");

    if cfg["BasePath"] != "":
        fpath = cfg["BasePath"]
    generate_PV_lexicon(inputLexName=inputlexname, fPath=fpath, config=cfg);
