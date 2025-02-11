"""
Created on Mon Feb 8 12:51:23 2021
Class to store a pronunciation with all rules that resulted in that pronunciation
@author: swekia
"""
from typing import Optional


class Pronunciation():
    def __init__(self, pron: str, rules: str):
        self.pron = pron;
        self.rules = rules;

    def __repr__(self):
        return 'Pronunciation: ' + str(self.pron) + ' <-- ' + str(self.rules);

    def __eq__(self, other):
        return self.pron == other.pron

    def add(self, addThis, addAsGroupOfRules: Optional[bool]=False):
        """
        This method appends a set of rules, no matter whether that rule is already in there.
        We need to append it anyway.
        """
        # if addThis not in self.ruleList:
        if addAsGroupOfRules:
            self.rules = self.rules + r' & ' + addThis;
        else:
            self.rules = self.rules + r'|' + addThis;
        return;

    def replace(self, pron, replaceBy):
        """
        This method replaces a given variant (i.e. canonical pronunciation) with the variant defined by 'replaceBy'.
        Should be used for final C 2 k and voiced 2 unvoiced s.
        Be careful! Don't use this method for other rules.
        """
        # if addThis not in self.ruleList:
        self.pron = pron;
        self.rules = replaceBy;
        return;