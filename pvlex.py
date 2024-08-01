import sys
import os
import json5 as json
import numpy as np
from utils.NewPronVarGenerator import PronVarGenerator
from g2p import g2p
import pandas as pd
from utils.lexicon_utils import *
import re


def generate_PV_lexicon(inputLexName, fPath, config={}, wantPVs=True) -> (dict, str):
    """
    Take (GRASS) wordlist and create pronunciation lexicon with:
    - canonical pronunciations
    and optionally:
    - pronunciation variants (PVs),
    - appending additional lexicons,
    - appending lexicons of other corpora with/without PVs,
    - reduce phone set
    - create Part-of-Speech (PoS) tags
    ... as defined in the config file.
    """

    # log file to track duplicate words (could be thrown out of additional lexicons if needed)
    logFile = open(f"{fPath}/PVGenerationAndWordsAlreadySeen.log", 'w', encoding='utf-8');

    # try to read in configuration if not gives as parameter
    if not config:
        try:
            # genpath = "pvlexicon/code"; @Julian: ggf. diese Zeile wieder reinnehmen
            genpath = sys.path[-1]
            configname = "config.json";
            # print(genpath)
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
        wordlistName = config["WordListName"]
        nWords = check_and_prepare_wordlist(fPath, wlName=wordlistName)

        # get canonical pronunciations from grapheme-to-phoneme (g2p) conversion tool
        parser = g2p.parser;
        print(os.path.join(config["BasePath"], wordlistName))
        mainLanguage = grasslang2g2plang(cfg["GeneralSettings"]["PronunciationSettings"]["LanguageTagsG2P"],
                                         config["MainLanguage"])
        args = parser.parse_args([os.path.join(fPath, wordlistName), '--iform=txt', '--oform=tab',
                                  '--stress=yes', '--syl=yes', f"--lng={mainLanguage}"])
        print(f"... using g2p for {mainLanguage} ({nWords} words) ...")
        g2pOutput = g2p.process(args);
        # postprocess raw g2p output
        lexiconRaw = postprocess_g2p(g2pOutput, fPath, inputLexName);

    # overwrite some wrong g2p pronunciations
    if config["GeneralSettings"]["overwritePronunciations"]["want2do"] is True:
        loadPath = '/'.join([fPath, "SpecialLexicons"]);
        lexiconRaw = overwrite_pronunciations(loadPath, lexiconRaw)

    # 2do: HIER
    # write homophone lexicon at this stage
    lexHomophonesOnly = get_homophones(lexiconRaw);
    write_homophone_lexicon(lexHomophonesOnly, inputLexName, fPath, nameExtension="Original");

    # initialise which rules should be applied, if any; see config file
    ruleSets = config["GeneralSettings"]["ruleSets"]
    rules = init_PV_rules(config['PronunciationVariation'], want2genPVs, ruleSets);

    # initialise PV generator
    PVGen = PronVarGenerator(lexName=strip_file_extension(config["OriginalLexiconName"]), rules=rules);
    PVGen.lexPath = fPath;

    # generate pronunciation variants
    PVGen.gen_pron_vars(lexiconRaw);
    PVGen.write_rule_count();
    PVGen.lexiconPVs = PVGen.sort_by_keys()
    # PVGen.lexiconPVs = PVGen.remove_duplicates_from_lexicon(PVGen.lexiconPVs);
    # PVGen.write_lexicon(nameExtension="_GermanOnly", case=config["GeneralSettings"]["case"]);

    # create a fesh copy of the current lexicon, then add others
    lexiconNew = copy.deepcopy(PVGen.lexiconPVs);
    write_lexicon(lexiconNew, f"{PVGen.lexiconName}_", fPath, case="lower")
    lexHomophonesOnly = get_homophones(lexiconNew);
    write_homophone_lexicon(lexHomophonesOnly, PVGen.lexiconName, fPath);

    # 2do: probably, we might want to add SOME dictionaries BEFORE PV generation but for the moment I don't do that
    #      because the special lexicons are lacking syllable information.
    # add Kiel and/or GECO if configured
    addToLexName = "";
    for lexName in config["addCorpora"].keys():
        if lexName.startswith('_'):  # skip comments in config file
            continue;
        addToLexName += '&' + lexName;
        if bool(config["addCorpora"][lexName]["want2add"]) is True:
            fname = config["addCorpora"][lexName]["fileName"];  # name of lexicon file if present
            try:
                fpath = config["addCorpora"][lexName]["filePath"];
            except KeyError:  # if no extra path defined, search this reps' data path for additional corpus files
                fpath = fPath;
            try:
                lines = open(os.path.join(fpath, fname), 'r', encoding='utf-8').readlines()
                lexTmp = {};
                for line in lines:
                    [k, v] = line.strip().split(r'{}'.format('\t'));
                    lexTmp.update({k: v});

            except FileNotFoundError:
                fname = config["addCorpora"][lexName]["wordListName"];
                try:
                    lexRawName = f"lexicon_{lexName}_canon.txt";
                    parser = g2p.parser;
                    print(os.path.join(fpath, fname))
                    args = parser.parse_args([os.path.join(fpath, fname), '--iform=txt', '--oform=tab',
                                              '--stress=yes', '--syl=yes', f"--lng=deu"])
                    print(f"... using g2p for {lexName} ...")
                    g2pOutput = g2p.process(args);
                    g2pOutputCrazy = g2pOutput.split('\n');
                    with open(f"{fpath}/{lexRawName}", 'w', encoding='utf-8') as f:
                        for line in sorted(g2pOutputCrazy):
                            if line:
                                f.write('\t'.join(line.split(';')) + '\n');
                    lexTmp = {};
                    with open(f"{fpath}/{lexRawName}", 'r', encoding='utf-8') as f:
                        tmp = f.read().splitlines();
                        for line in tmp:
                            k, v = line.split('\t')
                            lexTmp.update({k: v})

                except FileNotFoundError:
                    msg = f"\nCAUTION: you wanted to add '{lexName}' words but I couldn't find either \n" + \
                          f"a raw lexicon or a corresponding wordlist here:\n{os.path.join(fpath, fname)}\n" \
                          "so i'll just ignore that and move on\n"
                    logFile.writelines(msg);
                    print(msg);
            finally:

                rules = init_PV_rules(config['PronunciationVariation'],
                                      bool(config["addCorpora"][lexName]["generatePVs4thisLexicon"]));
                lexName = "lexicon_" + lexName;
                PVGenTmp = PronVarGenerator(lexName=lexName, rules=rules);
                PVGenTmp.lexPath = fPath;
                PVGenTmp.gen_pron_vars(lexTmp);
                PVGenTmp.write_lexicon()
                # lexTmp = read_lexicon(PVGenTmp.lexiconName + ".txt", fPath)
                # lex = read_lexicon(lexRawName, fPath);
                lexiconNew, logInfo = merge_lexicons(lexiconNew, PVGenTmp.lexiconPVs, lexName)
                # else:
                #     lexiconNew, logInfo = merge_lexicons(lexiconNew, lexTmp, lexName)
                if logInfo is not []:
                    logFile.writelines(logInfo);

    # save this lexicon state
    if len(lexiconNew) != len(PVGen.lexiconPVs):
        write_lexicon(lexiconNew, PVGen.lexiconName + addToLexName, fPath, case='lower')

    # append manual lexicons
    for key, val in config["SpecialLexicons"]["Lexicons"].items():
        # check whether variable is set true to append current special lexicon
        if bool(val["want2add"]) is True:
            fname = val["lexName"];
            try:
                lex = read_lexicon(fname, loadPath);
                lexName = re.sub(r"__(.*).txt", r"\1", fname);
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

    # convert all long vowels to short vowels; if that produced duplicates in the pronunciation, they were thrown
    if bool(config["GeneralSettings"]["convertLong2ShortVowels"]) is True:
        lexiconNew = long2shortVowels(lexiconNew);
        lexiconNew = convert2austrianPhones(lexiconNew, isPronLex=True);

    # 2do: it makes much more sense to do this minimisation before generation of PVs
    if bool(config["GeneralSettings"]["reducePhoneSet"]) is True:
        phonesToBeMerged = {}
        for key in config["GeneralSettings"]["PhoneSetMinimisation"]:
            if key.startswith('_'):  # skip comments in config file
                continue;
            phonesToBeMerged.update({str(key): str(config["GeneralSettings"]["PhoneSetMinimisation"][key])});
        lexiconNew = reduce_phone_set(lexiconNew, phonesToBeMerged);

    # sort dict before writing
    sort_regular_dict_by_key(lexiconNew);
    # write to file
    lexName = strip_file_extension(config["FinalLexiconName"]);
    write_lexicon(lexiconNew, lexName, fPath, case="lower")
    write_wordlist(lexiconNew, lexName, fPath)
    lexHomophonesOnly = get_homophones(lexiconNew);
    write_homophone_lexicon(lexHomophonesOnly, 'lexiconLatest', fPath);

    # 2do: below needs wordlists from annotationtools; so this script should export wordlist itself
    # if you want PoS tags, set wantPoS = True
    if config["GeneralSettings"]["wantPoS"] is True:
        # filepath = os.path.join(os.path.dirname(os.getcwd()), 'data', 'wordlist_caseSensitive.txt')
        fNames = [fn for fn in os.listdir(f"{os.path.join(fPath, 'WordLists')}") if fn.startswith("wordlist")];
        for fName in fNames:
            language = grasslang2g2plang(config, re.sub(r"wordlist([A-Z]+)\.txt", r"\1", fName));
            wordListPath = f"{fPath}/WordLists/{fName}";
            parser = g2p.make_parser();
            args = parser.parse_args([wordListPath, '--iform=txt', '--oform=extbpfs',
                                      '--stress=yes', '--syl=yes', f"--lng={language}"])
            print('using g2p now, might take a while ...')
            g2pOutput = g2p.process(args);
            g2pOutput = g2pOutput.split('\n');

            # initialise empty data frame for untangling g2p output
            PoS_DF = pd.DataFrame("", index=np.arange(0, int((len(g2pOutput) - 1) / 6)),
                                  columns=["ORT", "KAN", "POS", "KSS", "MRP", "TRL"]);

            for line in g2pOutput:
                if line:  # ignore empty lines
                    line = line.split(' ', 2);
                    # set this one cell in DF
                    PoS_DF.at[int(line[1]), line[0].strip(':')] = line[2];

            # write to file
            PoS_DF.to_csv(f"{fPath}/WordLists/PoS_{language}.csv", index=False);

    logFile.close();
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
