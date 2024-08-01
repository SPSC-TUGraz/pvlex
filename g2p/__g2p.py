"""
This web service converts an orthographic text input into a
canonical phonological transcript (standard pronunciation).

G2P (short for 'grapheme to phoneme conversion') reads a
continuous text or word list, and estimates the most likely
string of phonemes that a standard speaker of that language
is expected to articulate. G2P uses statistically trained
decision trees and some more tricks like Part-of-speech
tagging and morphological segmentation to improve the
decision process. Each language version of G2P is trained on
a large set of pronunciations from this language (a
pronunciation dictionary) or is based on a letter-sound
mapping table in case of simple unique correspondences. The
way G2P operates depends on numerous options and the chosen
input and output format. For instance, some input formats
contain non-tokenized text (e.g. txt) that will be subject to
tokenisation and normalisation, while others contain already
tokenized text (list,bpf) that will be processed as is. Most
output formats also come in an 'extended' version (indicated
by a 'ext' in the format name, e.g. 'exttab') that lists more
information than the the phonemic transcript; extended output
is only avaliable for a small subset of language yet.

For more detailed information about the methods G2P applies
please refer to: Reichel, U.D. (2012). PermA and Balloon:
Tools for string alignment and text processing, Proc. of the
Interspeech. Portland, Oregon, paper no. 346.
"""

import argparse
import requests
import xml.etree.ElementTree as ET


def str_to_bool(v):
    v = v.lower()
    if v in ("yes", "true", "t", "y", "1"):
        return True
    elif v in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")


def bool_to_yesno(b):
    if b:
        return "yes"
    else:
        return "no"


def make_parser():
    parser = argparse.ArgumentParser(
        description="convert an orthographic text into a canonical phonological transcript"
    )

    parser.add_argument("input_file", type=str)

    parser.add_argument(
        "--com",
        type=str_to_bool,
        help="whether <*> string should be treated as annotation markers",
        default=False,
    )

    parser.add_argument(
        "--tgrate",
        type=float,
        help=(
            "(only needed if iform=tg and oform=bpf(s)) "
            "sample rate of the corresponding speech signal"
        ),
        default=None,
    )

    parser.add_argument(
        "--stress",
        type=str_to_bool,
        help="whether or not word stress is to be added to the canonical transcription (KAN tier)",
        default=False,
    )

    lng_options = (
        "cat, deu, eng, fin, hat, hun, ita, mlt, nld, nze, pol, aus-AU, afr-ZA, sqi-AL, "
        "eus-ES, eus-FR, cat-ES, cze-CZ, nld-NL, eng-US, eng-AU, eng-GB, eng-NZ, ekk-EE, "
        "fin-FI, fra-FR, kat-GE, deu-DE, gsw-CH-BE, gsw-CH-BS, gsw-CH-GR, gsw-CH-SG, "
        "gsw-CH-ZH, gsw-CH, hat-HT, hun-HU, isl-IS, ita-IT, jpn-JP, gup-AU, ltz-LU, mlt-MT, "
        "nor-NO, pol-PL, ron-RO, rus-RU, slk-SK, spa-ES, swe-SE, tha-TH, guf-AU, und"
    ).split(", ")

    parser.add_argument("--lng", choices=lng_options, help="input language", default="deu")

    parser.add_argument(
        "--lowercase",
        type=str_to_bool,
        help="whether orthographic input is treated case sensitive (false) or not (true)",
        default=True,
    )

    parser.add_argument(
        "--syl",
        type=str_to_bool,
        help="whether or not the output transcription is to be syllabified",
        default=False,
    )

    outsym_options = "sampa, x-sampa, maus-sampa, ipa, arpabet".split(", ")

    parser.add_argument(
        "--outsym", choices=outsym_options, help="output phoneme symbol inventory", default="sampa"
    )

    parser.add_argument("--nrm", type=str_to_bool, help="text normalization", default=False)

    parser.add_argument(
        "--tgitem",
        type=str,
        help=(
            "(only needed if iform=tg) name of the TextGrid tier (item) that contains the words "
            "to be transcribed"
        ),
    )

    align_options = "yes, no, maus".split(", ")

    parser.add_argument(
        "--align",
        choices=align_options,
        help="whether or not the transcription is to be letter-aligned",
        default="no",
    )

    featset_options = "standard, extended".split(", ")

    parser.add_argument(
        "--featset",
        choices=featset_options,
        help="feature set used for grapheme-phoneme conversion",
        default="standard",
    )

    iform_options = "txt, bpf, list, tcf, tg".split(", ")

    parser.add_argument("--iform", choices=iform_options, help="input format", required=True)

    oform_options = (
        "txt, tab, exttab, lex, extlex, bpf, bpfs, extbpf, extbpfs, tcf, exttcf, tg, exttg".split(
            ", "
        )
    )

    parser.add_argument("--oform", choices=oform_options, help="output format", required=True)
    return parser


def process(args):
    with open(args.input_file, "r", encoding="utf-8") as f:
        post_request = requests.post(
            "https://clarin.phonetik.uni-muenchen.de/BASWebServices/services/runG2P",
            data={
                "com": bool_to_yesno(args.com),
                "tgrate": args.tgrate,
                "stress": bool_to_yesno(args.stress),
                "lng": args.lng,
                "lowercase": bool_to_yesno(args.lowercase),
                "syl": bool_to_yesno(args.syl),
                "outsym": args.outsym,
                "nrm": bool_to_yesno(args.nrm),
                "tgitem": args.tgitem,
                "align": args.align,
                "featset": args.featset,
                "iform": args.iform,
                "oform": args.oform,
            },
            files={"i": f},
        )

    # check response for HTTP status 400, otherwise raise expeption
    post_request.raise_for_status()

    root = ET.fromstring(post_request.text)
    if root.tag != "WebServiceResponseLink":
        raise RuntimeError("Unknown response type")

    if root.find("success").text != "true":
        raise RuntimeError("Could not perform service request")

    if (output := root.find("output").text) is not None:
        print("Output from service:", output.strip(), sep="\n")

    if (warnings := root.find("warnings").text) is not None:
        print("Warnings:", warnings.strip(), sep="\n")

    download_link = root.find("downloadLink").text
    get_request = requests.get(download_link)
    # print(get_request.text)
    return get_request.text


if __name__ == "__main__":
    parser = make_parser()
    args = parser.parse_args()
    with requests.Session() as s:
        process(s, args)
