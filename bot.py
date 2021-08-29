import discord
from discord.ext import commands, tasks
import os
from os import path
from xml.etree import ElementTree
import json
import glob
import re
from datetime import datetime, timedelta
import challonge
import requests
from random import randrange
import sys

intents = discord.Intents.default()
intents.members = True

client = commands.Bot(command_prefix = '-', case_insensitive=True, intents=intents)
validKeyWords=["cmc","o","t","c","-o","power","toughness","type","-c","-t","-type","p","is"]
valueKeyWords = ["cmc"]
tournamentData = None
cards = []

def updateJSON():
    with open('tournament.json', 'w') as file:
        json.dump({"data":tournamentData}, file)

@tasks.loop(minutes=1440.0)
async def called_once_a_day():
    clone()

@called_once_a_day.before_loop
async def before():
    await client.wait_until_ready()

async def checkToStartWeekly():
    tourney = tournamentData['weekly']
    weekday = datetime.today().weekday()
    hour = datetime.now().hour
    minute = datetime.now().minute
    channel = client.get_channel(795075875611607060)
    if weekday == 4 and hour == 14 and minute < 5:
        await channel.send("Don't forget, the weekly is starting in 4 hours! DM me '-registerweekly (decklist)' to sign up, replacing (decklist) with the decklist you want to use for the tournament.")
    elif weekday == 4 and hour == 18:
        if tourney != None:
            challongeTourney = challonge.tournaments.show(tourney['link'].rsplit('/', 1)[-1])
            if challongeTourney['started_at'] == None:
                if challongeTourney['participants_count'] < 2:
                    challonge.tournaments.destroy(challongeTourney['id'])
                    await channel.send("Tried to start a tournament with less than 2 people, tournament has been aborted.")
                    tournamentData['weekly'] = None
                    updateJSON()
                    return
                else:
                    try:
                        for player in tourney['players']:
                            if len(player['decklist']) == 52 and "https://tumbledmtg.com/decklist=" in player['decklist']:
                                continue
                            decklistLines = player['decklist'].splitlines()
                            firstLine = decklistLines[0]
                            title = ""
                            if firstLine[0:2] == "//" and (not ("Maindeck" in firstLine) or ("Sideboard" in firstLine)):
                                title = firstLine[3:]
                            else:
                                title = (str(challongeTourney['start_at'])[0:10] + " Weekly Decklist")
                            body = decklistRequest(title,
                                                      str(player['name']).split("#")[0], player['decklist'], player['id']).__dict__
                            r = requests.post('https://us-central1-tumbledmtg-website.cloudfunctions.net/api/decklistAdmin', json=body)
                            if 'decklist' in r.json():
                                print(r.json())
                                player['decklist'] = "https://tumbledmtg.com/decklist=" + str(r.json()['decklist']['decklistId'])
                            else:
                                print(r.json())
                    except Exception as e:
                        print(type(e))
                        print(e.args)
                        print(e)
                        await channel.send("Something went wrong when uploading player decklists. Idk what to do, everything is broken, someone please help I can't do this on my own.")
                        return
                    updateJSON()
                    challonge.tournaments.update(challongeTourney['id'], description=json.dumps(tourney['players']))
                    challonge.participants.randomize(challongeTourney['id'])
                    challonge.tournaments.start(challongeTourney['id'])
                    await channel.send("The weekly tournament is starting! Decklists have been uploaded.")

async def checkToEndWeekly():
    starData = [{"place": 1, "count" : 3}, {"place": 1, "count" : 5},{"place": 2, "count" : 6},{"place": 1, "count" : 7},{"place": 2, "count" : 8},{"place": 3, "count" : 10},{"place": 1, "count" : 12},{"place": 2, "count" : 14},{"place": 3, "count" : 16},{"place": 5, "count" : 18}]
    channel = client.get_channel(795075875611607060)
    tourney = tournamentData['weekly']
    weekday = datetime.today().weekday()
    hour = datetime.now().hour
    if tourney != None:
        challongeTourney = challonge.tournaments.show(tourney['link'].rsplit('/', 1)[-1])
        if challongeTourney['progress_meter'] == 100:
            challonge.tournaments.finalize(challongeTourney['id'])
            participants = challonge.participants.index(challongeTourney['id'])
            for i in range(len(starData)):
                if challongeTourney['participants_count'] < starData[i]['count']:
                    break
                else:
                    try:
                        for participant in participants:
                            if participant['final_rank'] == starData[i]['place']:
                                name = participant['name']
                                for player in tourney['players']:
                                    if player['name'] == name:
                                        r = requests.put("https://us-central1-tumbledmtg-website.cloudfunctions.net/api/stars/" + player['decklist'].rsplit('/', 1)[-1].split("=")[1], json={"inc" : 1, "id": player['id'], "password": password})
                                        if not 'success' in r.json():
                                            await channel.send("Unsuccessful star count update. 1")
                    except:
                        await channel.send("There was an error while updating star count, stars will have to be applied manually.")
                        break
            for participant in participants:
                for player in tourney['players']:
                    if player['name'] == participant['name']:
                        r2 = requests.post("https://us-central1-tumbledmtg-website.cloudfunctions.net/api/tourneyResults", json={"id": str(player['id']), "participants": challongeTourney['participants_count'], "placement": participant['final_rank'], "password": password, "url": challongeTourney["full_challonge_url"], "decklist": player['decklist'], 'date': str(challongeTourney['start_at'])[0:10]}) 
            await channel.send("The weekly has finished. You can see the results and decklists at https://tumbledmtg.com/tournament=" + str(challongeTourney['id']))
            tournamentData['weekly'] = None
            updateJSON()
            bigchannel = client.get_channel(326822492222128138)
            await bigchannel.send("The TumbledMTG weekly tournament just finished!\n\nCheck out the results and decklists used: <https://tumbledmtg.com/tournament=" + str(challongeTourney['id']) + ">\n\nA new single elimination tournament begins every Friday, free to enter with a 10$ prize!")
        elif weekday == 2 and hour == 17:
            await channel.send("The current weekly is taking too long, all remaining matches and stars will have to be updated manually. You can check out the bracket at " + tourney['link'])
            tournamentData['weekly'] = None
            updateJSON()
    else:
        try:
            if weekday == 2 and hour == 18:
                newChallongeTourney = challonge.tournaments.create(url="tbldmtgweekly" + str(datetime.today().strftime("%d_%m_%Y"))+ str(randrange(10000)), start_at= datetime.today() + timedelta((4-datetime.today().weekday()) % 7), name="TumbledMTG Weekly " + str(datetime.today() + timedelta((4-datetime.today().weekday()) % 7))[0:10])
                tournamentData['weekly'] = Tournament(newChallongeTourney['full_challonge_url']).__dict__
                updateJSON()
                await channel.send("The next weekly has been created. DM me '-registerweekly (decklist)' before Friday at 6pm PST to sign up, replacing (decklist) with the decklist you want to use for the tournament. You can find the bracket at " + newChallongeTourney['full_challonge_url'])
                secondchannel = client.get_channel(209040539339849729)
                await secondchannel.send("""Join the TumbledMTG weekly tournament!
Deadline to submit a decklist: Friday at 6pm (PST)

It's free to enter, single elimination structure played out over a couple days with 10$ prize. :money_with_wings: 

Browse the card pool: <https://tumbledmtg.com/search>
Grab a decklist: <https://tumbledmtg.com/decklists>
Download the auto-updating launcher: <https://tumbledmtg.com/>
Join the weekly: <https://tumbledmtg.com/tournaments>""")

        except Exception as e:
            print(e)

async def callMatches(tourney):
    if tourney != None:
        url = tourney['link'].rsplit('/', 1)[-1]
        challongeTourney = challonge.tournaments.show(url)
        matches = challonge.matches.index(challongeTourney['id'])
        for match in matches:
            if match['player1_id'] == None or match['player2_id'] == None:
                continue
            if match['underway_at'] == None:
                challonge.matches.mark_as_underway(challongeTourney['id'], match['id'])
                channel = client.get_channel(795075875611607060)
                guild = client.get_guild(455612893900308501)
                try:
                    player1 = str(challonge.participants.show(challongeTourney['id'],match['player1_id'])['name'])
                    player2 = str(challonge.participants.show(challongeTourney['id'],match['player2_id'])['name'])
                    await channel.send(guild.get_member_named(player1).mention + guild.get_member_named(player2).mention + " you two have a match!")
                except:
                    await channel.send("A match has started but one of the players was not found in this discord.")

@tasks.loop(minutes=5.0)
async def called_once_a_min():
    await checkToEndWeekly()
    await checkToStartWeekly()
    await callMatches(tournamentData['main'])
    await callMatches(tournamentData['weekly'])


@called_once_a_min.before_loop
async def before():
    await client.wait_until_ready()

@client.event
async def on_ready():
    if path.exists("tournament.json"):
        with open('tournament.json', 'r') as file:
            data = file.read()
            global tournamentData
            tournamentData = json.loads(data)['data']
            print(tournamentData)
    called_once_a_day.start()
    called_once_a_min.start()
    await client.change_presence(activity=discord.Game('https://tumbledmtg.com'))
    print('Bot is ready.')


@client.event
async def on_message(message):
    if message.author == client.user:
        return
    matches = re.findall('\[{.*?}\]',message.content)
    if len(matches) >= 10:
        await message.channel.send("Relax.")
        return
    for x in matches:
        count = 0
        founds = ""
        cardname = x[2:-2]
        words = cardname.split()
        keywords = []
        values = []
        searchwords = []
        for word in words:
            if not ":" in word:
                searchwords.append(word)
            else:
                halfs = word.split(":")
                keywords.append(halfs[0])
                values.append(halfs[1])
        for keyword in keywords:
            if not keyword in validKeyWords:
                founds+=keyword+" is not a valid keyword, type -keywords for a list of valid keywords\n"
                del values[keywords.index(keyword)]
                keywords.remove(keyword)
        if len(keywords) > 0 or len(searchwords) > 0:
            for c in cards:
                lol = True
                title = c.find('name').text
                for word in searchwords:
                    if word.lower() not in title.lower():
                        lol = False
                if not lol:
                    continue
                for i in range(len(keywords)):
                    if keywords[i] in valueKeyWords:
                        if values[i][0] == ">":
                            if not (c.find(keywords[i]).text > values[i][1:]):
                                lol = False
                                break
                        elif values[i][0] == "=":
                            if not (c.find(keywords[i]).text == values[i][1:]):
                                lol = False
                                break
                        elif values[i][0] == "<":
                            if not (c.find(keywords[i]).text < values[i][1:]):
                                lol = False
                                break
                        else:
                            if values[i].isnumeric():
                                if not (c.find(keywords[i]).text == values[i]):
                                    lol = False
                                    break
                            else:
                                lol = False
                                break
                    else:
                        try:
                            if keywords[i] == "-c":
                                colors = c.find('color').text.lower()
                                for letter in values[i].lower():
                                    if letter in colors:
                                        lol = False
                                        break
                                if not lol:
                                    break
                            elif keywords[i] == "c":
                                colors = c.find('color').text.lower()
                                if values[i][0] == "=":
                                    for letter in values[i].lower():
                                        if letter == "=":
                                            continue
                                        else:
                                            if not letter in colors:
                                                lol = False
                                                break
                                    if "h" in colors:
                                        break
                                    if not (len(colors) == len(values[i])) and not (colors.length == 1):
                                        lol = False
                                    break
                                for letter in values[i].lower():
                                    if not letter in colors:
                                        lol = False
                                        break
                                if not lol:
                                    break
                            elif keywords[i] == "o":
                                text = c.find('text').text.lower()
                                if "," in values[i]:
                                    thevalue = values[i].replace(","," ")
                                    if (thevalue.startswith("'") and thevalue.endswith("'")) or (thevalue.startswith('"') and thevalue.endswith('"')):
                                        thevalue = thevalue[2:-2]
                                        if not thevalue in text:
                                            lol = False
                                        break
                                    else:
                                        thevalue = values[i].replace(","," ").split(" ")
                                        for word in thevalue:
                                            if not word in text:
                                                lol = False
                                                break
                                        break
                                if not values[i].lower() in text:
                                    lol = False
                                    break
                            elif keywords[i] == "-o":
                                text = c.find('text').text.lower()
                                if values[i].lower() in text:
                                    lol = False
                                    break
                            elif keywords[i] == "t" or keywords[i] == "type":
                                type = c.find('type').text.lower()
                                if not values[i].lower() in type:
                                    lol = False
                                    break
                            elif keywords[i] == "-t" or keywords[i] == "-type":
                                type = c.find('type').text.lower()
                                if values[i].lower() in type:
                                    lol = False
                                    break
                            elif keywords[i] == "power" or keywords[i] == "p":
                                power = c.find('pt').text
                                power = power[0]
                                if values[i][0] == ">":
                                    if not (power > values[i][1:]):
                                        lol = False
                                        break
                                elif values[i][0] == "=":
                                    if not (power == values[i][1:]):
                                        lol = False
                                        break
                                elif values[i][0] == "<":
                                    if not (power < values[i][1:]):
                                        lol = False
                                        break
                                else:
                                    if values[i].isnumeric():
                                        if not (power == values[i]):
                                            lol = False
                                            break
                                    else:
                                        lol = False
                                        break
                            elif keywords[i] == "toughness":
                                toughness = c.find('pt').text
                                toughness = toughness[2]
                                if values[i][0] == ">":
                                    if not (toughness > values[i][1:]):
                                        lol = False
                                        break
                                elif values[i][0] == "=":
                                    if not (toughness == values[i][1:]):
                                        lol = False
                                        break
                                elif values[i][0] == "<":
                                    if not (toughness < values[i][1:]):
                                        lol = False
                                        break
                                else:
                                    if values[i].isnumeric():
                                        if not (toughness == values[i]):
                                            lol = False
                                            break
                                    else:
                                        lol = False
                                        break
                            elif keywords[i] == "is":
                                if values[i] == "new":
                                    new = c.find('new').text
                                    if not new == "TRUE":
                                        lol = False
                                else:
                                    lol = False
                        except:
                            lol = False
                            break

                if not lol:
                    continue
                founds += c.find('name').text + "\n"
                count+=1
                if count == 20:
                    founds+="And more!\n"
                    break
        if len(founds) > 0:
            await message.channel.send(founds)
        else:
            await message.channel.send("Could not find cards for search " + x[2:-2] +", note that most searches need a colon (ex. cmc:>3 rather than cmc>3)")
    matches = re.findall('\{\[.*?\]\}', message.content)
    if len(matches) > 5:
        await message.channel.send("Relax.")
        return
    for x in matches:
        lol = False
        cardname = x[2:-2]
        for c in cards:
            if (cardname.lower() in c.find('name').text.lower()) or (c.find('related') != None and cardname.lower() in c.find('related').text.lower()):
                lol = True
                cardfile = "./TumbledMTG-Cockatrice/data/pics/CUSTOM/"
                cardfile += c.find('name').text
                cardfile += ".jpg"
                await message.channel.send(file=discord.File(cardfile))
                if c.find('related') != None:
                    cardfile = "./TumbledMTG-Cockatrice/data/pics/CUSTOM/"
                    cardfile += c.find('related').text
                    cardfile += ".jpg"
                    await message.channel.send(file=discord.File(cardfile))
                break
        if lol == False:
            await message.channel.send("Could not find card " + x)
    await client.process_commands(message)

@client.command()
@commands.has_permissions(administrator=True)
async def update(ctx):
    clone()
    await ctx.send("Updated.")

@client.command()
async def updatestars(ctx, decklist, stars):
    if str(ctx.author) != "Tumbles#3232":
        return
    try:
        decklistid = decklist.rsplit('/', 1)[-1].split("=")[1]
        r = requests.put("https://us-central1-tumbledmtg-website.cloudfunctions.net/api/stars/" + decklistid, json={"inc": stars, "password": password})
        if 'success' in r.json():
            await ctx.send("Successfully updated stars.")
        else:
            await ctx.send("Response returned errors.")
    except:
        await ctx.send("Error sending response.")

@client.command()
async def deletedecklist(ctx, decklist):
    if not (str(ctx.author) == "Tumbles#3232" or str(ctx.author) == "Big Money#7196"):
        return
    decklistid = decklist.rsplit('/', 1)[-1].split("=")[1]
    try:
        r = requests.delete("https://us-central1-tumbledmtg-website.cloudfunctions.net/api/deldecklist/" + decklistid, headers={"password": password})
        if "success" in r.json():
            await ctx.send("Successfully updated stars.")
        else:
            print(r.json()['error'])
            await ctx.send("Failed to update stars.")
    except:
        await ctx.send("Request error.")

def clone():
    dir = os.getcwd()
    os.chdir('./TumbledMTG-Cockatrice')
    os.system("git pull")
    os.chdir(dir)
    dom = ElementTree.parse("./TumbledMTG-Cockatrice/data/customsets/tumbled-mtg-cards.xml")
    global cards
    cards = dom.find('cards')
    cards = cards.findall('card')


@client.command()
async def newtournament(ctx, arg):
    if str(ctx.guild) == "TumbledMTG" and (str(ctx.author) == "Tumbles#3232" or str(ctx.author) == "BigMoney#7196"):
        if tournamentData['main'] == None:
            try:
                tournamentData['main'] = Tournament(arg).__dict__
                tourney = challonge.tournaments.show(tournamentData['main']['link'].rsplit('/', 1)[-1])
                updateJSON()
                await ctx.send("Tournament started with name " + tourney["name"] +", scheduled for " + str(tourney['start_at']))
            except Exception as e:
                print(e)
                tournamentData['main'] = None
                updateJSON()
                await ctx.send("Failed, likely a challonge error.")
        else:
            await ctx.send("Tournament already in progress")

@client.command()
async def registertourney(ctx, *, args):
    # update this too
    decklist = args
    tourney = tournamentData['main']
    if tourney != None:
        try:
            challongeTourney = challonge.tournaments.show(tourney['link'].rsplit('/', 1)[-1])
        except:
            await ctx.send("Error getting challonge bracket, please try again.")
            return
        if challongeTourney['started_at'] == None:
            body = decklistRequest((str(challongeTourney['start_at'])[0:10] + " Weekly Decklist"),
                                              str(ctx.author).split("#")[0], decklist).__dict__
            print(body)
            r = requests.post('https://us-central1-tumbledmtg-website.cloudfunctions.net/api/testdecklist',
                              json=body)
            if 'errors' in r.json():
                print(r.json())
                await ctx.send("Invalid decklist: " +r.json()['errors'])
                return
            elif 'success' in r.json():
                await ctx.send("Decklist is valid!")
            else:
                await ctx.send("Server error, I think... you have not been registered, try again maybe? If this happens more than once then call for help.")
                print(r.json())
                return
            try:
                challonge.participants.create(challongeTourney['id'], str(ctx.author))
                tourney['players'].append(Player(str(ctx.author), decklist).__dict__)
                updateJSON()
                await ctx.send("Added you to the bracket!")
                channel = client.get_channel(795075875611607060)
                await channel.send(str(ctx.author) + " has registered for the tournament!")
            except:
                await ctx.send("There was an error, either you are already registered or challonge failed to respond.")
        else:
            await ctx.send("The tournament has already started.")
    else:
        await ctx.send("There is no tournament to register for!")

@client.command()
async def registerweekly(ctx, *, args):
    decklist = args
    tourney = tournamentData['weekly']
    if tourney != None:
        try:
            challongeTourney = challonge.tournaments.show(tourney['link'].rsplit('/', 1)[-1])
        except:
            await ctx.send("Error getting challonge bracket, please try again.")
            return
        if challongeTourney['started_at'] == None:
            req = requests.get('https://us-central1-tumbledmtg-website.cloudfunctions.net/api/user/' + str(ctx.author.id))
            if 'error' in req.json():
                if req.json()['error'] == "Could not find user.":
                    await ctx.send("You must create an account on https://tumbledmtg.com before you can register for a tournament.")
                else:
                    await ctx.send("Error getting data, please try again later.")
                return
            elif 'username' in req.json():
                if "https://tumbledmtg.com/decklist=" in decklist:
                    if len(decklist) == 52:
                        rr = requests.get("https://us-central1-tumbledmtg-website.cloudfunctions.net/api/validateDecklist/"+decklist.split("=")[1])
                        if 'success' in rr.json():
                            await ctx.send("Decklist is valid!")
                        elif rr.status_code == 404:
                            await ctx.send("You linked to a decklist that does not exist")
                            return 
                        else:
                            await ctx.send("Unknown error. Please try again.")
                            return
                    else: 
                        await ctx.send("Invalid decklist link.")
                        return
                else:
                    body = decklistRequest((str(challongeTourney['start_at'])[0:10] + " Weekly Decklist"),
                                        str(ctx.author).split("#")[0], decklist, str(ctx.author.id)).__dict__
                    r = requests.post('https://us-central1-tumbledmtg-website.cloudfunctions.net/api/testdecklist',
                                    json=body)
                    if 'errors' in r.json():
                        print(r.json())
                        await ctx.send("Invalid decklist: " + str(r.json()['errors']))
                        return
                    elif 'success' in r.json():
                        await ctx.send("Decklist is valid!")
                    else:
                        await ctx.send("Server error, I think... you have not been registered, try again maybe? If this happens more than once then call for help.")
                        print(r.json())
                        return
                try:
                    for player in tourney['players']:
                        if player['name'] == str(ctx.author):
                            tourney['players'].remove(player)
                            tourney['players'].append(Player(str(ctx.author), decklist, str(ctx.author.id)).__dict__)
                            updateJSON()
                            await ctx.send("You are already registered for this tournament, your decklist has been replaced.")
                            return
                except:
                    await ctx.send("Tell Big Money that his code sucks")
                try:
                    challonge.participants.create(challongeTourney['id'], str(ctx.author))
                    tourney['players'].append(Player(str(ctx.author), decklist, str(ctx.author.id)).__dict__)
                    updateJSON()
                    await ctx.send("Added you to the bracket!")
                    channel = client.get_channel(795075875611607060)
                    await channel.send(str(ctx.author) + " has registered for the weekly!")
                except:
                    await ctx.send("There was an error, challonge probably failed to respond. Maybe try again, and if it doesn't work then call for help.")
            else:
                await ctx.send("Fatal error, please contact a mod.")
        else:
            await ctx.send("The tournament has already started.")
    else:
        await ctx.send("There is no tournament to register for!")

@client.command()
async def unregisterweekly(ctx):
    tourney = tournamentData['weekly']
    for player in tourney['players']:
        if player['name'] == str(ctx.author):
            try:
                challongeTourney = challonge.tournaments.show(tourney['link'].rsplit('/', 1)[-1])
                participants = challonge.participants.index(challongeTourney['id'])
            except:
                await ctx.send("Error getting challonge bracket, please try again.")
                return
            if challongeTourney['started_at'] == None:
                for participant in participants:
                    if participant['name'] == str(ctx.author):
                        try:
                            challonge.participants.destroy(challongeTourney['id'], participant['id'])
                        except:
                            await ctx.send("Error removing you from the challonge tourney")
                            return
                        tourney['players'].remove(player)
                        updateJSON()
                        await ctx.send("Successfully removed you from bracket.")
                        return
            else:
                await ctx.send("Tournament has already started.")
                return
    await ctx.send("You are not signed up for the current weekly.")



@client.command()
async def deletetourney(ctx):
    if str(ctx.guild) == "TumbledMTG" and str(ctx.author) == "Tumbles#3232":
        if tournamentData['main'] != None:
            tournamentData['main'] = None
            updateJSON()
            await ctx.send("No longer looking at active tourney")
        else:
            await ctx.send("There is no active tourney to delete")

@client.command()
async def DQweekly(ctx):
    tourney = tournamentData['weekly']
    try:
        challongeTourney = challonge.tournaments.show(tourney['link'].rsplit('/', 1)[-1])
        participants = challonge.participants.index(challongeTourney['id'])
        matches = challonge.matches.index(challongeTourney['id'])
    except:
        await ctx.send("Error getting challonge bracket, please try again.")
        return
    if challongeTourney['started_at'] != None:
        for participant in participants:
            if participant['name'] == str(ctx.author):
                id = participant['id']
                p2id = 0
                score = ""
                for match in matches:
                    if match['player1_id'] == id:
                        p2id = match['player2_id']
                        score = "0-69"
                    elif match['player2_id'] == id:
                        p2id = match['player1_id']
                        score = "69-0"
                    if not (p2id == None or p2id == 0):
                        print(p2id)
                        challonge.matches.update(challongeTourney['id'],match['id'],score_cv=score,winner_id=p2id)
                        await ctx.send("You have been DQ'd")
                        return
        await ctx.send("You do not currently have a match to DQ from.")

@client.command()
async def resetpassword(ctx, username, newpassword):
    if str(ctx.guild) == "TumbledMTG":
        await ctx.send("Not here not here not here")
        return
    data = {
        "id": str(ctx.author.id),
        "username": username,
        "newPassword": newpassword,
        "password": password
    }
    r = requests.post("https://us-central1-tumbledmtg-website.cloudfunctions.net/api/resetPassword", json=data)
    if 'success' in r.json():
        await ctx.send("Successfully updated your password.")
    elif 'error' in r.json():
        await ctx.send(r.json()['error'])
    else:
        await ctx.send("Something went wrong, probably a server error.")

async def reportScores(ctx, args, tourney):
    if len(args) != 2:
        await ctx.send("Invalid report syntax.")
        return
    score = args[0]
    opponent = ctx.message.mentions[0]
    if opponent == None:
        await ctx.send("Invalid opponent.")
        return
    if len(score) != 3:
        await ctx.send("Invalid score syntax!")
        return
    playerscore = score[0]
    opponentscore = score[2]
    if not playerscore.isnumeric() or not opponentscore.isnumeric() or score[1] != "-":
        await ctx.send("Invalid score syntax.")
        return
    if playerscore == "0" and opponentscore == "0":
        await ctx.send("I'm not submitting this score and you can't make me.")
        return
    if playerscore == opponentscore:
        await ctx.send("Why are you submitting a tie, why why why why why why why why why why.")
        return
    opponent = opponent.name + "#" + str(opponent.discriminator)
    player = ctx.author.name + "#" + str(ctx.author.discriminator)
    tourney = tournamentData['weekly']
    try:
        challongeTourney = challonge.tournaments.show(tourney['link'].rsplit('/', 1)[-1])
        matches = challonge.matches.index(challongeTourney['id'])
        participants = challonge.participants.index(challongeTourney['id'])
    except:
        await ctx.send("Challonge failed to respond, please try again.")
        return
    playerid = ""
    opponentid = ""
    try:
        for participant in participants:
            if participant['name'] == player:
                playerid = participant['id']
            elif participant['name'] == opponent:
                opponentid = participant['id']
    except:
        await ctx.send("Error parsing tourney participants, most likely a challonge error, try again.")
        return
    lol = False
    try:
        for match in matches:
            if match['winner_id'] != None or match['state'] != "open":
                continue
            if match['player1_id'] == playerid and match['player2_id'] == opponentid:
                if playerscore > opponentscore:
                    challonge.matches.update(challongeTourney['id'], match['id'], scores_csv=score, winner_id=playerid)
                    lol = True
                    break
                else:
                    challonge.matches.update(challongeTourney['id'], match['id'], scores_csv=score, winner_id=opponentid)
                    lol = True
                    break
            elif match['player1_id'] == opponentid and match['player2_id'] == playerid:
                score = score[-1] + score[1:-1] + score[0]
                if playerscore > opponentscore:
                    challonge.matches.update(challongeTourney['id'], match['id'], scores_csv=score, winner_id=playerid)
                    lol = True
                    break
                else:
                    challonge.matches.update(challongeTourney['id'], match['id'], scores_csv=score, winner_id=opponentid)
                    lol = True
                    break
    except Exception as e:
        print(e)
        await ctx.send("Error updating scores, probably a challonge error. Try again, and if it happens again, call for help.")
        return
    if not lol:
        await ctx.send("Error updating scores, could not find a match between these 2 players.")
        return
    await ctx.send("Scores have successfully been submitted!")

@client.command()
async def weeklyreport(ctx, *args):
    tourney = tournamentData['weekly']
    reportScores(ctx, args, tourney)

@client.command()
async def uploaddecklists(ctx):
    #update this whole function
    if str(ctx.guild) == "TumbledMTG" and str(ctx.author) == "Tumbles#3232":
        tourney = tournamentData['main']
        try:
            challongeTourney = challonge.tournaments.show(tourney['link'].rsplit('/', 1)[-1])
        except:
            await ctx.send("Challonge server error, please try again.")
            return
        try:
            for player in tourney['players']:
                body = decklistRequest("Tourney Decklist",
                                       str(player['name']).split("#")[0], player['decklist'], player['id']).__dict__
                r = requests.post('https://us-central1-tumbledmtg-website.cloudfunctions.net/api/decklist', json=body)
                if 'decklist' in r.json():
                    player['decklist'] = "https://tumbledmtg.com/decklist=" + str(r.json()['decklist']['id'])
                else:
                    print(r.json())
        except:
            await ctx.send("Something went wrong when uploading player decklists. Idk what to do, everything is broken, someone please help I can't do this on my own.")
            return
        updateJSON()
        try:
            challonge.tournaments.update(challongeTourney['id'], description=json.dumps(tourney['players']))
        except:
            await ctx.send("Challonge server error when updating description, everything else worked I think, but descrition will have to be updated manually.")
            return
        await ctx.send("Decklists have been uploaded!")

@client.command()
async def tourneyreport(ctx, *args):
    tourney = tournamentData['main']
    reportScores(ctx,args,tourney)

@client.command()
async def tags(ctx):
    tagsList = []
    for card in cards:
        tags = card.find('tags')
        if tags is not None:
            if tags.text is not None:
                for tag in tags.text.split():
                    if not tag in tagsList:
                        tagsList.append(tag)
                        tagsList.append("\n")
    tagsList.pop()
    await ctx.send("".join(tagsList))

@client.command()
async def keywords(ctx):
    await ctx.send("c:(colors) for colors\no:(word) for oracle text\ncmc:(sign)(value) for cmc\nt:(type) for type\npower:(sign)(value) for power\ntoughness:(sign)(value) for toughness\ncan also use - before c, o, and t to search for opposite\nany other words without a colon are searched for in card title")

token = ""
apikey = ""
password = ""

class Tournament:
    def __init__(self, link):
        self.link = link
        self.players = []

class Player:
    def __init__(self, name, decklist, id):
        self.name = name
        self.decklist = decklist
        self.id = id

class decklistRequest:
    def __init__(self, title, author, body, id):
        self.title = title
        self.author = author
        self.body = body
        self.description = "This decklist was automatically generated by the discord bot."
        self.id = id
        self.password = password

with open('config.json', 'r') as file:
    data = file.read()
    file_dict = json.loads(data)
    token = file_dict["token"]
    apikey = file_dict["challongeAPIKey"]
    password = file_dict["password"]
challonge.set_credentials("TumbledMTG", apikey)
client.run(token)
