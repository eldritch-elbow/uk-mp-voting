import datetime
import mysql.connector
import sys
import itertools
import networkx as nx

# 2010-05-06 - coalition start
# 2005-05-05 - labour 3
# 2001-06-07 - labour 2



# Support functions

def edge_key( mp_tuple ):
  mp1 = mp_tuple[0]
  mp2 = mp_tuple[1]
  return ( min(mp1, mp2), max(mp1, mp2) )

def normalize_vote(vote):
  if (vote == "tellaye"):
    vote = "aye"
  if (vote == "tellno"):
    vote = "no"
  if (vote == "both"):
    vote = "abstention"
  return vote

def percentage_for(divs_for, divs_against, division, party):

    for_    = divisions_for[division][party]
    against = divisions_against[division][party]

    active_votes = for_ + against

    # Eliminate small parties (quoram per vote is five)
    if active_votes < 5: 
      return -1

    return int ( (float(for_) / float(active_votes)) * 100 )

def rebelling(divs_for, divs_against, division, party, vote):

  pc_for = percentage_for(divs_for, divs_against, division, party)

  if pc_for == -1:
    return False
  elif vote == "aye" and pc_for < 10:
    return True
  elif vote == "no" and pc_for > 90:
    return True
  else:
    return False

def print_histogram(hist_data, name):
  print 
  print "*** Histogram: {} ***".format(name)
  print
  print "PC\tCount"  
  for (p,c) in enumerate(hist_data):
    print "{}\t{}".format(p,c)
  print

def output_graph(mps, mp_data, edges):

  G=nx.Graph()

  # Define the nodes
  for mp in mps:
    G.add_node(mp, label=mp_data[mp]["name"], party=mp_data[mp]["party"], constituency=mp_data[mp]["constituency"])

  # Process all known edges
  for (mp_tuple,agr_data) in edges.items():

    agreements = agr_data[0]
    agreement_rate = agr_data[2]

    # Depending on the selection criteria, filter out relationships
    if agreement_rate < 85:
      continue    

    # Determine a (normalized) weight, again depending on the desired graph
    # edge_wt = agreements
    range_min = 85
    range_max = 100
    weight_base = agreement_rate - range_min
    edge_wt = ( float(weight_base) / float(range_max - range_min) )

    G.add_edge(mp_tuple[0],mp_tuple[1], agreement=agreement_rate, weight=edge_wt )

  nx.write_graphml(G, "mp_agreement.graphml")





cnx = mysql.connector.connect(user='mpdata', database='public_whip')
cursor = cnx.cursor()

DIV_SQL = ("select division_id from pw_division "
           "where division_date > '2010-05-06' and house='commons' " )

###########################
# Read relevant divisions #
###########################
divisions = set()

query = (DIV_SQL);
print query
cursor.execute(query)

for (row) in cursor:
  divisions.add( row[0] )

####################
# Read sitting MPs #
####################
mps = set()

query = ("select distinct pw_mp.mp_id from pw_vote, pw_mp "
         "where pw_vote.mp_id = pw_mp.mp_id "
         "and division_id in ( "+DIV_SQL+" )");
print query
cursor.execute(query)

for (row) in cursor:
  mps.add( row[0] )



################
# Read MP data #
################
mp_data = {}
all_parties = set()

query = ("select mp_id, first_name, last_name, title, constituency, party from pw_mp") 
print query
cursor.execute(query)

for (row) in cursor:
  mp_data[ row[0] ] = { "name": "{}, {}".format(row[2], row[1]), "constituency" : row[4], "party" : row[5] } 
  all_parties.add(row[5])

print all_parties



#####################################
# Count number of MPs in each party #
#####################################
party_counts = {}
for party in all_parties:
  party_counts[party] = 0
for mp in mps:
  mp_rec = mp_data[mp]
  party_counts[ mp_rec["party"] ] += 1

print 
print "Party counts:"
print
for (party,count) in party_counts.items():
  print "{}\t{}".format(party, count)
print

##################################
# Read all votes for sitting MPs #
##################################
votes = {}

query = ("select mp_id, division_id, vote from pw_vote "
         "where division_id in ( "+DIV_SQL+" )")
print query
cursor.execute(query)

for (row) in cursor:

  voting_mp = row[0]
  division = row[1]
  vote = row[2]

  if voting_mp in mps and division in divisions:

    if voting_mp not in votes:
      votes[voting_mp] = {}
    
    votes[voting_mp][division] = vote



#######################################
# Read whip / majority data per party #
#######################################
divisions_for     = {} 
divisions_against = {} 

for division in divisions:

  votes_for     = {} # By party
  votes_against = {} # By party

  for party in all_parties:
    votes_for[party]     = 0
    votes_against[party] = 0

  for mp in mps:
    mp_votes = votes[mp]

    if division not in mp_votes:
      continue

    mp_vote  = normalize_vote( mp_votes[division] )
    mp_party = mp_data[mp]["party"]

    # Record for or against - ignore abstention / spoiled / missing
    if mp_vote == "aye":
      votes_for[mp_party] += 1
    elif mp_vote == "no":
      votes_against[mp_party] += 1

  divisions_for[division]     = votes_for
  divisions_against[division] = votes_against


# Create a histogram of voting %ages across all divisions and parties
hist = 101 * [0]
for division in divisions:
  for party in all_parties:

    pc_for = percentage_for(divisions_for, divisions_against, division, party)

    if pc_for == -1:
      continue

    hist[ pc_for ] += 1

print_histogram(hist, "Percentages for divisions")



##########################
# Now find relationships #
##########################
edges = {}
uncountable = {"abstention", "both", "spoiled"}

for mp_tuple in itertools.product(mps, mps):

  if mp_tuple[0] == mp_tuple[1]:
    continue

  key = edge_key(mp_tuple)
  if key in edges:
    continue

  mpA = mp_tuple[0]
  mpB = mp_tuple[1]
  mpA_party = mp_data[mpA]["party"]
  mpB_party = mp_data[mpB]["party"]
  mpA_votes = votes[mpA]
  mpB_votes = votes[mpB]

  matches = 0
  agreement = 0

  for (division,mpA_vote) in mpA_votes.items():

    if division not in mpB_votes:
      continue

    mpA_vote = normalize_vote(mpA_vote)
    mpB_vote = normalize_vote(mpB_votes[division])
    matches += 1

    # Skip abstentions and spoiled ballots
    if (mpA_vote in uncountable or mpB_vote in uncountable):
      continue

    # Now decide whether there's a relationship:
    # a_rebelling = rebelling(divisions_for, divisions_against, division, mpA_party, mpA_vote)
    # b_rebelling = rebelling(divisions_for, divisions_against, division, mpB_party, mpB_vote)
    # if (a_rebelling and b_rebelling and mpB_vote == mpA_vote):
    #   agreement += 1

    if (mpB_vote == mpA_vote):
      agreement += 1

    # print "{}:{} @ div {}: {} / {}. Agr={}".format(mp_tuple[0], mp_tuple[1], division, mpA_vote, mpB_vote, agreement)

  agreement_rate = 0
  if matches > 0:    
    agreement_rate = int (  (float(agreement) / float(matches)) * 100  )

  edges[key] = (agreement, matches, agreement_rate)
  print "{}: {} / {}".format(key, agreement, matches)




# Summarize agreement rates
hist = 101 * [0]
for agr_data in edges.values():
  hist[ agr_data[2] ] += 1

print_histogram(hist, "Agreement")



# Output the graph
output_graph(mps, mp_data, edges)









cursor.close()
cnx.close()





