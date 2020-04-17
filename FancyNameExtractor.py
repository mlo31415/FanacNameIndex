from __future__ import annotations
from typing import Optional, Dict

import os
import re

from F3Page import F3Page, DigestPage
from Log import Log, LogOpen, LogSetHeader
from HelpersPackage import WindowsFilenameToWikiPagename, SearchAndReplace
from FanzineIssueSpecPackage import FanzineDateRange, FanzineDate

# The goal of this program is to produce an index to all of the names on Fancy 3 and fanac.org with links to everything interesting about them.
# We'll construct a master list of names with a preferred name and zero or more variants.
# This master list will be derived from Fancy with additions from fanac.org
# The list of interesting links will include all links in Fancy 3, and all non-housekeeping links in fanac.org
#   A housekeeping link is one where someone is credited as a photographer or having done scanning or the like
# The links will be sorted by importance
#   This may be no more than putting the Fancy 3 article first, links to fanzines they edited next, and everything else after that

# The strategy is to start with Fancy 3 and get that working, then bring in fanac.org.
# This program produces a comprehensive index on Fancy 3, including a list of all people names n Fancy 3.
# This is written to files which are used as input to the indexer for Fanac.org which produces the final result.

# We'll work entirely on the local copies of the two sites.

# For Fancy 3 on MediaWiki, there are many names to keep track of for each page:
#       The actual, real-world name.  But this can't always be used for a filename on Windows or a page name in Mediawiki, so:
#       WikiPagename -- the name of the MediaWiki page it was created with and as it appears in a simple Mediawiki link.
#       URLname -- the name of the Mediawiki page in a URL
#                       Basically, spaces are replaced by underscores and the first character is always UC.  #TODO: What about colons? Other special characters?
#       WindowsFilename -- the name of the Windows file in the in the local site: converted using methods in HelperPackage. These names can be derived from the Mediawiki page name and vice-versa.
#       WikiDisplayname -- the display name in MediaWiki: Normally the name of the page, but can be overridden on the page using DISPLAYTITLE
#
#       The URLname and WindowsFilename can be derived from the WikiPagename, but not necessarily vice-versa

#TODO: Revise this

# There will be a dictionary, nameVariants, indexed by every form of every name. The value will be the canonical form of the name.
# There will be a second dictionary, people, indexed by the canonical name and containing an unordered list of Reference structures
# A Reference will contain:
#       The canonical name
#       The as-used name
#       An importance code (initially 1, 2 or 3 with 3 being least important)
#       If a reference to Fancy, the name of the page (else None)
#       If a reference to fanac.org, the URL of the relevant page (else None)
#       If a redirect, the redirect name

fancySitePath=r"C:\Users\mlo\Documents\usr\Fancyclopedia\Python\site"   # A local copy of the site maintained by FancyDownloader
LogOpen("Log", "Error", dated=True)

# The local version of the site is a pair (sometimes also a folder) of files with the Wikidot name of the page.
# <name>.txt is the text of the current version of the page
# <name>.xml is xml containing meta date. The metadata we need is the tags
# If there are attachments, they're in a folder named <name>. We don't need to look at that in this program

# Create a list of the pages on the site by looking for .txt files and dropping the extension
Log("***Querying the local copy of Fancy 3 to create a list of all Fancyclopedia pages")
Log("   path='"+fancySitePath+"'")
allFancy3PagesFnames = [f[:-4] for f in os.listdir(fancySitePath) if os.path.isfile(os.path.join(fancySitePath, f)) and f[-4:] == ".txt"]
allFancy3PagesFnames = [cn for cn in allFancy3PagesFnames if not cn.startswith("index_")]     # Drop index pages
#allFancy3PagesFnames= [f for f in allFancy3PagesFnames if f[0] in "ab"]        # Just to cut down the number of pages for debugging purposes
Log("   "+str(len(allFancy3PagesFnames))+" pages found")

fancyPagesDictByWikiname={}     # Key is page's canname; Val is a FancyPage class containing all the references on the page

Log("***Scanning local copies of pages for links")
for pageFname in allFancy3PagesFnames:
    if pageFname.startswith("Log 202"):     # Ignore Log files in the site directory
        continue
    val=DigestPage(fancySitePath, pageFname)
    if val is not None:
        fancyPagesDictByWikiname[val.Name]=val
Log("   "+str(len(fancyPagesDictByWikiname))+" semi-unique links found")

# Analyze the conseries pages and extract conventions from it
Log("***Analyzing convention series tables")
conventions={}  # We use a dictionary to eliminate duplicates
for page in fancyPagesDictByWikiname.values():
    if "Conseries" in page.Categories:
        LogSetHeader("Processing conseries "+page.Name)
        if page.Table is not None:
            if "Convention" in page.Table.Headers:
                concol=page.Table.Headers.index("Convention")
            elif "Name" in page.Table.Headers:
                concol=page.Table.Headers.index("Name")
            else:
                Log("***No column 'Convention(s)' in conseries "+page.Name, isError=True)
                continue

            if "Date" in page.Table.Headers:
                datecol=page.Table.Headers.index("Date")
            elif "Dates" in page.Table.Headers:
                datecol=page.Table.Headers.index("Dates")
            else:
                Log("***No column 'Date(s)' in conseries "+page.Name, isError=True)
                continue

            for row in page.Table.Rows:
                if concol < len(row) and len(row[concol]) > 0  and datecol < len(row) and len(row[datecol]) > 0:
                    # Ignore anything in trailing parenthesis
                    p=re.compile("\(.*\)\s?$")
                    datestr=p.sub("", row[datecol])
                    fdr=FanzineDateRange().Match(datestr)
                    if fdr.IsEmpty():
                        Log("***Could not interpret "+row[concol]+"'s date range: "+row[datecol])
                    else:
                        if fdr.Duration() > 6:
                            Log("??? "+page.Name+" has long duration: "+str(fdr))
                        conventions[row[concol].lower()+str(fdr._startdate.Year)]=((row[concol], fdr))      # We merge conventions with the same name and year


# Convert the con dictionary to a list and sort it in date order
conventions=[c for c in conventions.values()]
conventions.sort(key=lambda d: d[1])

# List the conventions
Log("Writing: Convention timeline.txt")
with open("Convention timeline.txt", "w+", encoding='utf-8') as f:
    for con in conventions:
        f.write(str(con[1])+": "+str(con[0])+"\n")

Log("Writing Convention timeline (Fancy).txt")
with open("Convention timeline (Fancy).txt", "w+", encoding='utf-8') as f:
    currentYear=None
    currentDateRange=None
    f.write("<tab>\n")
    for con in conventions:
        if currentYear == con[1]._startdate.Year:
            if currentDateRange == con[1]:
                f.write("&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;' ' ||"+str(con[0])+"\n")
            else:
                f.write(str(con[1])+"||"+str(con[0])+"\n")
                currentDateRange=con[1]
        else:
            currentYear = con[1]._startdate.Year
            currentDateRange=con[1]
            f.write('colspan="2"| '+"<big><big>'''"+str(currentYear)+"'''</big></big>\n")
            f.write(str(con[1])+"||"+str(con[0])+"\n")
    f.write("</tab>")

Log("***Computing redirect structure")
# A FancyPage has an UltimateRedirect which can only be filled in once all the redirects are known.
# Run through the pages and fill in UltimateRedirect.
def GetUltimateRedirect(fancyPagesDictByWikiname: Dict[str, F3Page], redirect: str) -> str:
    assert redirect is not None
    if redirect not in fancyPagesDictByWikiname.keys():  # Target of redirect does not exist, so this redirect is the ultimate redirect
        return redirect
    if fancyPagesDictByWikiname[redirect] is None:       # Target of redirect does not exist, so this redirect is the ultimate redirect
        return redirect
    if fancyPagesDictByWikiname[redirect].Redirect is None: # Target is a real page, so that real page is the ultimate redirect
        return fancyPagesDictByWikiname[redirect].Name

    return GetUltimateRedirect(fancyPagesDictByWikiname, fancyPagesDictByWikiname[redirect].Redirect)

# Fill in the UltimateRedirect element
num=0
for fancyPage in fancyPagesDictByWikiname.values():
    if fancyPage.Redirect is not None:
        num+=1
        fancyPage.UltimateRedirect=GetUltimateRedirect(fancyPagesDictByWikiname, fancyPage.Redirect)
Log("   "+str(num)+" redirects found", Print=False)

# OK, now we have a dictionary of all the pages on Fancy 3, which contains all of their outgoing links
# Build up a dictionary of redirects.  It is indexed by the canonical name of a page and the value is the canonical name of the ultimate redirect
# Build up an inverse list of all the pages that redirect *to* a given page, also indexed by the page's canonical name. The value here is a list of canonical names.
redirects={}            # Key is the name of a redirect; value is the ultimate destination
inverseRedirects={}     # Key is the name of a destination page, value is a list of names of pages that redirect to it
for fancyPage in fancyPagesDictByWikiname.values():
    if fancyPage.Redirect is not None:
        if fancyPage.Redirect is not None:  # A page has an UltimateRedirect iff it has a Redirect
            assert fancyPage.UltimateRedirect is not None
        else:
            assert fancyPage.UltimateRedirect is None
        redirects[fancyPage.Name]=fancyPage.UltimateRedirect
        if fancyPage.Redirect not in inverseRedirects.keys():
            inverseRedirects[fancyPage.Redirect]=[]
        inverseRedirects[fancyPage.Redirect].append(fancyPage.Name)
        if fancyPage.UltimateRedirect not in inverseRedirects.keys():
            inverseRedirects[fancyPage.UltimateRedirect]=[]
        if fancyPage.UltimateRedirect != fancyPage.Redirect:
            inverseRedirects[fancyPage.UltimateRedirect].append(fancyPage.Name)

# Create a dictionary of page references for people pages.
# The key is a page's canonical name; the value is a list of pages at which they are referenced.

# First locate all the people and create empty entries for them
peopleReferences={}
Log("***Creating dict of people references")
for fancyPage in fancyPagesDictByWikiname.values():
    if fancyPage.IsPerson():
        if fancyPage.Name not in peopleReferences.keys():
            peopleReferences[fancyPage.Name]=[]

# Now go through all outgoing references on the pages and add those which reference a person to that person's list
for fancyPage in fancyPagesDictByWikiname.values():
    if fancyPage.OutgoingReferences is not None:
        for outRef in fancyPage.OutgoingReferences:
            if outRef.LinkWikiName in peopleReferences.keys():    # So it's a people
                peopleReferences[outRef.LinkWikiName].append(fancyPage.Name)

Log("***Writing reports")
# Write out a file containing canonical names, each with a list of pages which refer to it.
# The format will be
#     **<canonical name>
#     <referring page>
#     <referring page>
#     ...
#     **<cannonical name>
#     ...
Log("Writing: Referring pages.txt")
with open("Referring pages.txt", "w+", encoding='utf-8') as f:
    for person, referringpagelist in peopleReferences.items():
        f.write("**"+person+"\n")
        for pagename in referringpagelist:
            f.write("  "+pagename+"\n")

# Now a list of redirects.
# We use basically the same format:
#   **<target page>
#   <redirect to it>
#   <redirect to it>
# ...
# Now dump the inverse redirects to a file
Log("Writing: Redirects.txt")
with open("Redirects.txt", "w+", encoding='utf-8') as f:
    for redirect, pages in inverseRedirects.items():
        f.write("**"+redirect+"\n")
        for page in pages:
            f.write("      ⭦ "+page+"\n")

# Next, a list of redirects with a missing target
Log("Writing: Redirects with missing target.txt")
allFancy3Pagenames=[WindowsFilenameToWikiPagename(n) for n in allFancy3PagesFnames]
with open("Redirects with missing target.txt", "w+", encoding='utf-8') as f:
    for key in redirects.keys():
        dest=redirects[key]
        if dest not in allFancy3Pagenames:
            f.write(key+" --> "+dest+"\n")


# Create and write out a file of peoples' names. They are taken from the titles of pages marked as fan or pro

# Ambiguous names will often end with something in parenthesis which need to be removed for this particular file
def RemoveTrailingParens(s: str) -> str:
    return re.sub("\s\(.*\)$", "", s)       # Delete any trailing ()

# Some names are not worth adding to the list of people names.  Try to detect them.
def IsInterestingName(p: str) -> bool:
    if " " not in p and "-" in p:   # We want to ignore names like "Bob-Tucker" in favor of "Bob Tucker"
        return False
    if " " in p:                    # If there are spaces in the name, at least one of them needs to be followed by a UC letter
        if re.search(" ([A-Z]|de|ha|von|Č)", p) is None:  # We want to ignore "Bob tucker"
            return False
    return True


Log("Writing: Peoples names.txt")
peopleNames=[]
# First make a list of all the pages labelled as "fan" or "pro"
with open("Peoples rejected names.txt", "w+", encoding='utf-8') as f:
    for fancyPage in fancyPagesDictByWikiname.values():
        if fancyPage.IsPerson():
            peopleNames.append(RemoveTrailingParens(fancyPage.Name))
            # Then all the redirects to one of those pages.
            if fancyPage.Name in inverseRedirects.keys():
                for p in inverseRedirects[fancyPage.Name]:
                    if p in fancyPagesDictByWikiname.keys():
                        peopleNames.append(RemoveTrailingParens(fancyPagesDictByWikiname[p].UltimateRedirect))
                        if IsInterestingName(p):
                            peopleNames.append(p)
                        else:
                            f.write("Uninteresting: "+p+"\n")
                    else:
                        Log("Generating Peoples names.txt: "+p+" is not in fancyPagesDictByWikiname")
            else:
                f.write(p+" Not in inverseRedirects.keys()\n")


# De-dupe it
peopleNames=list(set(peopleNames))

with open("Peoples names.txt", "w+", encoding='utf-8') as f:
    peopleNames.sort(key=lambda p: p.split()[-1][0].upper()+p.split()[-1][1:]+","+" ".join(p.split()[0:-1]))    # Invert so that last name is first and make initial letter UC.
    for name in peopleNames:
        f.write(name+"\n")
i=0


