"""Source registry + classification rules for Events Radar."""

# Devpost public hackathon API — paginated; we walk this many pages (≈ 10/page… actually 10-ish)
DEVPOST_PAGES = 8
DEVPOST_URL = "https://devpost.com/api/hackathons?status[]=open&status[]=upcoming&page={page}"

# MLH season schedule (schema.org microdata on every card)
MLH_SEASONS = [2027]
MLH_URL = "https://www.mlh.com/seasons/{season}/events"

# GitHub-maintained lists of programs (parsed by section)
GITHUB_LISTS = [
    ("zapplyjobs underclassmen programs", "https://raw.githubusercontent.com/zapplyjobs/underclassmen-internships/main/README.md", "zapply"),
]

# Firm pages that sometimes list dated events. The generic page scanner pulls any
# link that sits next to a date. Empty results are normal when nothing is posted.
FIRM_EVENT_PAGES = [
    ("Citadel", "https://www.citadel.com/careers/programs-and-events/"),
    ("Citadel Securities", "https://www.citadelsecurities.com/careers/programs-and-events/"),
    ("Jane Street", "https://www.janestreet.com/join-jane-street/programs-and-events/"),
    ("Optiver", "https://optiver.com/working-at-optiver/events/"),
    ("IMC Trading", "https://www.imc.com/us/events"),
    ("Susquehanna (SIG)", "https://careers.sig.com/events"),
    ("Hudson River Trading", "https://www.hudsonrivertrading.com/student-opportunities/"),
    ("Flow Traders", "https://www.flowtraders.com/careers/events"),
    ("D. E. Shaw", "https://fellowships.deshaw.com/"),
    ("Google", "https://buildyourfuture.withgoogle.com/events"),
    ("JPMorgan", "https://careers.jpmorgan.com/us/en/students/events"),
    ("Goldman Sachs", "https://www.goldmansachs.com/careers/students/events"),
    ("Bloomberg", "https://www.bloomberg.com/company/careers/early-career/events/"),
]

# Only keep hackathons in the US or online (per Akshita's choice)
US_STATES = {"AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC"}
US_STATE_NAMES = ["alabama","alaska","arizona","arkansas","california","colorado","connecticut","delaware","florida","georgia","hawaii","idaho","illinois","indiana","iowa","kansas","kentucky","louisiana","maine","maryland","massachusetts","michigan","minnesota","mississippi","missouri","montana","nebraska","nevada","new hampshire","new jersey","new mexico","new york","north carolina","north dakota","ohio","oklahoma","oregon","pennsylvania","rhode island","south carolina","south dakota","tennessee","texas","utah","vermont","virginia","washington","west virginia","wisconsin","wyoming"]

# Track detection on title + description
TRACK_RULES = [
    ("Quant",   [r"\bquant", r"\btrading\b", r"\btrader\b", r"\bmarket[- ]mak", r"\bhedge fund\b", r"\bderivativ", r"\bputnam\b", r"\bmath(ematic)?s?\b"]),
    ("AI/ML",   [r"\bai\b", r"\bmachine learning\b", r"\bml\b", r"\bdata scien", r"\bdatathon\b", r"\bllm", r"\bgenerative\b", r"\bdeep learning\b", r"\bnlp\b", r"\bcomputer vision\b", r"\bkaggle\b"]),
    ("SWE",     [r"\bsoftware\b", r"\bengineer", r"\bhack(athon)?\b", r"\bcod(e|ing)\b", r"\bdevelop", r"\bprogramm", r"\bopen source\b", r"\bweb\b", r"\bapp\b", r"\bcs\b", r"\bcomputer science\b", r"\btech"]),
    ("Finance", [r"\bfinanc", r"\bbank", r"\binvest", r"\bmarkets\b", r"\bequit", r"\basset management\b"]),
]

# Titles matching these are dropped (not relevant to SWE/AI/quant students)
EXCLUDE = [r"\bblockchain summit\b", r"\bweb3 summit\b", r"\bcrypto conference\b", r"\bk-?12\b", r"\bhigh school(ers)?\b", r"\bmiddle school\b", r"\bkids\b"]

HUBS = [
    ("Pittsburgh", [r"\bpittsburgh\b"]),
    ("New York",   [r"\bnew york\b", r"\bnyc\b", r"\bmanhattan\b", r"\bbrooklyn\b", r"\bjersey city\b", r", ny\b"]),
    ("Chicago",    [r"\bchicago\b", r", il\b", r"\bevanston\b"]),
    ("Bay Area",   [r"\bsan francisco\b", r"\bsf\b", r"\bbay area\b", r"\bberkeley\b", r"\bstanford\b", r"\bpalo alto\b", r"\bmountain view\b", r"\bsan jose\b", r"\bmenlo park\b", r"\bsunnyvale\b"]),
    ("Boston",     [r"\bboston\b", r"\bcambridge\b", r", ma\b"]),
    ("Philadelphia", [r"\bphiladelphia\b", r"\bbala cynwyd\b", r", pa\b"]),
    ("DC / Baltimore", [r"\bwashington, dc\b", r"\bdc\b", r"\bbaltimore\b", r"\barlington\b", r", md\b", r", va\b"]),
    ("Texas",      [r"\baustin\b", r"\bhouston\b", r"\bdallas\b", r", tx\b", r"\btexas\b"]),
    ("Los Angeles", [r"\blos angeles\b", r"\bla\b", r"\bpasadena\b", r"\bsanta monica\b"]),
    ("Seattle",    [r"\bseattle\b", r"\bredmond\b", r"\bbellevue\b", r", wa\b"]),
    ("Atlanta",    [r"\batlanta\b", r", ga\b"]),
    ("Toronto / Waterloo", [r"\btoronto\b", r"\bwaterloo\b", r"\bontario\b"]),
    ("Other US",   [r"\bunited states\b", r"\busa?\b"] + [rf", {s.lower()}\b" for s in ["az","co","ct","fl","in","ia","ks","ky","mi","mn","mo","nc","nj","oh","or","ri","sc","tn","ut","wi","nh","ne","nm","ok","al","ar","de","hi","id","la","me","ms","mt","nd","nv","sd","vt","wv","wy","ak"]]),
    ("Online",     [r"\bonline\b", r"\bvirtual\b", r"\beverywhere\b", r"\bworldwide\b", r"\bremote\b", r"\bdigital\b"]),
]

ELIGIBILITY_RULES = [
    ("Freshman",  [r"\bfirst[- ]year", r"\bfreshm[ae]n\b"]),
    ("Sophomore", [r"\bsecond[- ]year", r"\bsophomore"]),
    ("Junior",    [r"\bpenultimate\b", r"\bjuniors?\b", r"\bthird[- ]year"]),
    ("PhD",       [r"\bph\.?d\b", r"\bpostdoc"]),
    ("Undergrad", [r"\bundergrad", r"\bbachelor"]),
    ("Students",  [r"\bstudents?\b", r"\buniversity\b", r"\bcollege\b"]),
]
