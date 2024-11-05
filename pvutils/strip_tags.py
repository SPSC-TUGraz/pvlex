# -*- coding: utf-8 -*-
"""
Created on Mon May 25 10:40:46 2020
Funtion strip_tags(somestring). 
@author: kia
"""

import re


def strip_tags(stringin, speakingStyle='RS'):
    """
    This function removes tags, special characters, remaining underscores and
    multiple spaces from strings

    Parameters
    ----------
    stringin : string
        some string potentially containing special characters or 
        punctuation marks

    Returns
    -------
    stringout: string
        string without punctuation or multiple spaces

    """
    if speakingStyle == 'RS':
        # remove tags before removing symbols; tags are marked between "<" and ">"
        stringtmp = re.sub('<[^>]+>', '', stringin);
        # remove special characters while NOT splitting between apostrophe and hyphens
        stringtmp = re.sub('([a-zA-Z])-(?=[a-zA-Z])', r'\1', stringtmp)
        stringtmp = re.sub('([a-zA-Z])-(?=[a-zA-Z])', r'\1', stringtmp)
        stringtmp = re.sub(r'[^\w]', ' ', stringtmp);
        # remove remaining underscores
        stringtmp = re.sub('_', ' ', stringtmp)
        # remove multiple spaces
        stringout = ' '.join(stringtmp.split());
    elif speakingStyle == 'CS':
        # remove multiple spaces
        stringout = ' '.join(stringin.split());
    else:
        raise("invalid speakingStyle: " + speakingStyle);
    
    return stringout;