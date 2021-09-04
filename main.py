import discord
import os
import requests
import json
import random
from PIL import Image
from discord.ext import commands
from keep_alive import keep_alive
from datetime import datetime
import pytz
from datetime import timedelta
import asyncio
from pokereval.card import Card
from operator import itemgetter
from pokereval.hand_evaluator import HandEvaluator

random.seed()
intents = discord.Intents.default()
intents.members = True
client = commands.Bot(command_prefix="$", intents = intents)
deck_image = Image.open('deck.png')

@client.event
async def on_ready():
  print("Bot is up and running")
  #await check()
  asyncio.create_task(check())
  #asyncio.create_task(currency_update())

async def return_card_name(card : str):
  temp_num = int(card[0:2])
  number = str(temp_num)
  suit = card[2]
  if suit == '1':
    suit = "Hearts"
  elif suit == '2':
    suit = "Spades"
  elif suit == '3':
    suit = "Diamonds"
  elif suit == '4':
    suit = "Clubs"
  
  if number == '14':
    number = "Ace"
  elif number == '11':
    number = "Jack"
  elif number == '12':
    number = "Queen"
  elif number == '13':
    number = "King"
  card_name = number + " of " + suit
  return card_name


async def hand_value(hand : list, community : list):
  hole = []
  # player hand
  for value in hand:
    number = int(value[0:2])
    suit = int(value[2])
    card = Card(number, suit)
    hole.append(card)

  board = []
  # board
  for value in community:
    number = int(value[0:2])
    suit = int(value[2])
    card = Card(number, suit)
    board.append(card)
  
  score = HandEvaluator.evaluate_hand(hole, board)
  return score
  
  
@client.command(brief="Allows you to type to other people in your game")
async def gamechat(ctx, *, message):
  member = str(ctx.message.author.id)
  with open("games.json","r") as file:
    try:
      games = json.load(file)
    except:
      await ctx.message.author.send("**No games found**")
      return
  game_id = ""
  for game in games:
    if member in games[game]['members']:
      game_id = game
  if game_id == "":
    await ctx.message.author.send("**You are not in a game**")
    return
  for member_id in games[game]['members']:
    player_obj = await client.fetch_user(int(member_id))
    await player_obj.send(f"*{ctx.message.author.name}: {message}*")
  

async def random_card(deck):
  deck_length = len(deck)
  index = random.randint(0,deck_length-1)
  return index


async def getCoords(face_num,suit_num):
  if(face_num == 14):
    face_num = 1
  coords = (((face_num-1)*225), ((suit_num-1)*315),((face_num)*225), (((suit_num))*315))
  return coords


async def getCommunity(cards):
  height = 315
  width = 225 * len(cards)

  river_image = Image.new('RGBA', (width, height), (0,0,0, 0))

  for x in range(0, len(cards)):
    card_temp = deck_image.crop(await getCoords(int(cards[x][0:2]), int(cards[x][2])))
    river_image.paste(card_temp,(225*x, 0), mask=card_temp)
  
  river_image.save("community.png", format="png")
  card_temp.close()
  river_image.close()


async def generateHandImage(face_1, suit_1, face_2, suit_2):
  card1_img = deck_image.crop(await getCoords(face_1, suit_1))
  card2_img = deck_image.crop(await getCoords(face_2, suit_2))

  card1_img = card1_img.convert("RGBA")
  card2_img = card2_img.convert("RGBA")


  hand = Image.new('RGBA', (285, 395), (0,0,0, 0))
  hand.paste(card1_img,(0,0), mask=card1_img)
  hand.paste(card2_img, (60, 80),mask=card2_img)
  hand.save("player_hand.png", format="png")
  hand.close()


@client.command(brief="Used to interact with games (use \"%help game\" for more)", description="Poker Actions:\n\nStart: The owner of the game can use this to start the game.\nCheck: Passes your turn.\nRaise: Raises the bet of the current turn. Everyone must pay this amount to keep playing. Use \"%game raise <amount>\".\nCall : Allows you to pay for the previous bet or blind to keep playing.\nFold : Give up on the current round.\nPot  : Display the pot of the current round.\nHand : Display your current hand.\nRiver: Display the current community cards.")
async def game(ctx, action : str, amount : int=0):
  action = action.lower()
  member = str(ctx.message.author.id)
  sender = ctx.message.author
  game = ""
  with open("games.json","r") as file:
    try:
      games = json.load(file)
    except:
      await sender.send("**No games found**")
      return
  with open("bank.json", "r") as file:
    try:
      bank = json.load(file)
    except:
      print("ERROR: There are no members in the bank")
  # check if member is in a game
  for game in games:
    if member in games[game]['members']:
      game_id = game
  if game == "":
    await sender.send("**You are not in a game**")
    return
  members_obj = []
  for member_id in games[game]['members']:
    player_obj = await client.fetch_user(int(member_id))
    members_obj.append(player_obj)
  # retrieve variables
  game_name = games[game_id]['game']
  members_array = list(games[game_id]['members'].keys())
  member_name = ctx.message.author.name
  owner = await client.fetch_user(int(members_array[0]))
  member_money = int(bank[member][0])
  member_debt = int(games[game_id]['members'][member]['debt'])
  curr_pot = int(games[game_id]['pot'])
  started = False
  total_players = len(members_array)
  turn = int(games[game_id]['turn'])

  for player in members_array:
    if games[game_id]['members'][player]['hand'] != []:
      started = True
  turn_next = (turn + 1) % total_players
  while games[game_id]['members'][members_array[turn_next]]['hand'] == [] and started:
    turn_next = (turn_next + 1) % total_players
  prev_turn = (turn - 1) % total_players
  while games[game_id]['members'][members_array[prev_turn]]['hand'] == [] and started:
    prev_turn = (prev_turn - 1) % total_players
  
  async def next_turn():
    curr_turn = games[game_id]['turn']
    draw = True if games[game_id]['go_to'] == curr_turn else False
    turn = turn_next
    total_players = len(members_array)
    end = True if len(games[game_id]['community_cards']) == 5  and draw else False
    total_playing = 0
    curr_pot = int(games[game_id]['pot'])
    show_hand = True
    for player in members_array:
      if games[game_id]['members'][player]['hand'] != []:
        total_playing += 1
    if total_playing == 1:
      end = True
      draw = True
      show_hand = False
      games[game_id]['community_cards'] = ["064", "084", "094", "104", "114"]
    start = int(games[game_id]['start'])
    if games[game_id]['loop_count'] == '2':
      games[game_id]['loop_count'] = '0'
      draw = True
    # new round
    if draw:
      games
      # pick community cards
      if games[game_id]['community_cards'] == []:
        community_cards = []
        for x in range(3):
          index = await random_card(games[game_id]['deck'])
          games[game_id]['community_cards'].append(games[game_id]['deck'][index])
          card = games[game_id]['deck'].pop(index)
          card_name = await return_card_name(card)
          community_cards.append(card_name)
        
        community = ""
        for card_num, card in enumerate(community_cards):
          if card_num != 2:
            community += card + ", "
          else:
            community += "and a " + card + "!"
        await getCommunity(games[game_id]['community_cards'])
        current_turn_name = await client.fetch_user(int(members_array[turn]))
        # send message to each player
        for player in members_obj:
          file_com = discord.File("community.png", filename="image.png")
          embed = discord.Embed(title="Community cards", color=discord.Color.dark_red())
          embed.set_image(url="attachment://image.png")
          await player.send(f"**The community cards are {community}**")
          await player.send(file=file_com, embed=embed)
          await player.send(f"*It is now {current_turn_name.name}'s turn*")
          
      
      # normal round with card draw
      elif not end:
        index = await random_card(games[game_id]['deck'])
        games[game_id]['last_raise'] = '0'
        games[game_id]['community_cards'].append(games[game_id]['deck'][index])
        card = games[game_id]['deck'].pop(index)
        card = await return_card_name(card)
        current_turn_name = await client.fetch_user(int(members_array[turn]))

        #file_img = discord.File("player_hand.png", filename="image.png")
        #embed = discord.Embed(title="Your hand", color=discord.Color.dark_red())
        #embed.set_image(url="attachment://image.png")
        await getCommunity(games[game_id]['community_cards'])
        # send message to each player
        for player in members_obj:
          file_img2 = discord.File("community.png", filename="image.png")
          embed2 = discord.Embed(title="Community cards", color=discord.Color.dark_red())
          embed2.set_image(url="attachment://image.png")
          await player.send(f"**The {card} was drawn for the community cards**")
          #await player.send(file=file_img, embed=embed)
          await player.send(file=file_img2, embed=embed2)
          await player.send(f"*It is now {current_turn_name.name}'s turn*")

      # end of game sequence
      else:
        scores = []
        # get scores of all players
        for player in members_array:
          # creates score for each remaining player in game
          if games[game_id]['members'][player]['hand'] != []:
            new_score = (player, await hand_value(games[game_id]['members'][player]['hand'], games[game_id]['community_cards']))
            scores.append(new_score)
        max_score = str(max(scores, key=itemgetter(1))[1])
        winners = []
        # will create list of all winners
        for index,score in enumerate(scores):
          if score[1] == float(max_score):
            winners.append(score)
        winner_pot = round(curr_pot / len(winners))
        # interact with each winner
        for winner in winners:
          winner_id = winner[0]
          current_winner = await client.fetch_user(int(winner_id))
          for player in members_obj:
            await player.send(f"***{current_winner.name} won the game for ${curr_pot}!***")
          winner_money = int(bank[winner_id][0])
          winner_money += winner_pot
          bank[winner_id][0] = str(winner_money)
        # finish game
        bankrupt = []
        # update each player
        for member in games[game_id]['members']:
          games[game_id]['members'][member]['debt'] = '0'
          games[game_id]['members'][member]['hand'] = []
          if int(bank[member][0]) != 0:
            games[game_id]['members'][member]['status'] = 'Playing'
          else:
            bankrupt.append(member.name)
            games[game_id]['members'].pop(member)
            total_players -= 1
        # reset poker game
        games[game_id]['community_cards'] = []
        games[game_id]['go_to'] = games[game_id]['start']
        games[game_id]['start'] = str(turn_next)
        games[game_id]['pot'] = '0'
        games[game_id]['turn'] = str(turn_next)
        games[game_id]['last_raise'] = '0'
        games[game_id]['deck'] = ['021','031','041','051','061','071','081','091','101','111','121','131','141','022','032','042','052','062','072','082','092','102','112','122','132','142','023','033','043','053','063','073','083','093','103','113','123','133','143','024','034','044','054','064','074','084','094','104','114','124','134','144']
        # send update to each player
        for player in members_obj:
          if bankrupt != []:
            for member in bankrupt:
              await player.send(f"**{member} wen't bankrupt :(**")
          if(total_players >= 2):
            await player.send(f"**{owner.name} can start a new game or end this lobby with '%game end'**")
          else:
            await player.send(f"**Game over! Not enough people to play.**")
        if total_players < 2:
          games.pop(game_id)
        with open("games.json","w") as file:
          json.dump(games, file)
        with open("bank.json","w") as file:
          json.dump(bank, file)
        return
    else:
      #if games[game_id]['start'] == str(turn)
      #  games[game_id]['loop_count'] = str(int(games[game_id]['loop_count']) + 1)
      # turn with no draw
      current_turn_name = await client.fetch_user(int(members_array[turn]))
      for player in members_obj:
        await player.send(f"*It is now {current_turn_name.name}'s turn*")
    games[game_id]['turn'] = str(turn)
    games[game_id]['start'] = str(start)
    with open("games.json","w") as file:
      json.dump(games, file)
    with open("bank.json","w") as file:
      json.dump(bank, file)
    return
  

  # different actions
  if action == 'start':
    if started:
      await sender.send("*Game has already started*")
      return
    if member == members_array[0]:
      if not started and len(games[game_id]['members']) > 1:
        
        games[game_id]['go_to'] = str(prev_turn)
        start = int(games[game_id]['start'])
        big = start
        little = turn_next
        big_member = await client.fetch_user(int(members_array[big]))
        small_member = await client.fetch_user(int(members_array[little]))
        for player_index,player in enumerate(members_obj):
          # sending messages to all players
          if player_index == big:
            # big blind
            games[game_id]['members'][str(player.id)]['debt'] = '500'
          elif player_index == little:
            # little blind
            games[game_id]['members'][str(player.id)]['debt'] = '250'
          await player.send(f"**{member_name} has started the {game_name} game!\nThe big blind is {big_member.name} ($500) and the small blind is {small_member.name} ($250)**")

          # give players starting hand card1
          index = await random_card(games[game_id]['deck'])
          games[game_id]['members'][str(player.id)]['hand'].append(games[game_id]['deck'][index])
          card1 = games[game_id]['deck'].pop(index)
          card1_name = await return_card_name(card1)

          # give players starting hand card2
          index = await random_card(games[game_id]['deck'])
          games[game_id]['members'][str(player.id)]['hand'].append(games[game_id]['deck'][index])
          card2 = games[game_id]['deck'].pop(index)
          card2_name = await return_card_name(card2)
          await player.send(f"**You drew a {card1_name} and a {card2_name}!**\n*It is now {members_obj[turn].name}'s turn*")

          # generate image of hand
          await generateHandImage(int(card1[0:2]), int(card1[2]), int(card2[0:2]), int(card2[2]))
          file_img = discord.File("player_hand.png", filename="image.png")
          embed = discord.Embed(title="Your hand", color=discord.Color.dark_red())
          embed.set_image(url="attachment://image.png")
          await player.send(file=file_img, embed=embed)

        # update hands and deck
      else: await sender.send("*You need at least 2 players in the lobby or the game has already started*")
    else: await sender.send(f"*Only the owner of the game ({owner.name}) can do that*")
  
  elif action == 'pot':
    await sender.send(f"*The current pot is ${games[game_id]['pot']}*")
  
  elif action == 'hand' and started:
    if games[game_id]['members'][member]['hand'] != []:
      card1 = games[game_id]['members'][member]['hand'][0]
      card2 = games[game_id]['members'][member]['hand'][1]
      card1_name = await return_card_name(card1)
      card2_name = await return_card_name(card2)
      await generateHandImage(int(card1[0:2]), int(card1[2]), int(card2[0:2]), int(card2[2]))
      hand_img = discord.File("player_hand.png", filename="image.png")
      embed = discord.Embed(title="Your hand", color=discord.Color.dark_red())
      embed.set_image(url="attachment://image.png")
      await sender.send(f"**You have a {card1_name} and a {card2_name}.**")
      await sender.send(file=hand_img, embed=embed)
    else:
      await sender.send(f"*Your hand is empty*")
  
  elif action == 'river' and started:
    river = games[game_id]['community_cards']
    if river != []:
      await getCommunity(river)
      file_com = discord.File("community.png", filename="image.png")
      embed = discord.Embed(title="Community cards", color=discord.Color.dark_red())
      embed.set_image(url="attachment://image.png")
      community_cards = []
      for card in river:
        card_name = await return_card_name(card)
        community_cards.append(card_name)

        community = ""
      for card_num, card in enumerate(community_cards):
        if card_num != len(community_cards) - 1:
          community += card + ", "
        else:
          community += "and a " + card
      await sender.send(f"**The community cards are {community}.**")
      await sender.send(file=file_com, embed=embed)
    else: await sender.send("*There are no community cards*")
  
  elif action == 'end':
    if member == members_array[0] and not started:
      for player in members_obj:
        await player.send(f"***{member_name} has ended the game***")
      games.pop(game_id)
    elif member != members_array[0]:
      await sender.send(f"*Only the owner of the game ({owner.name}) can do that before the round has started*")
    else:
      await sender.send("*You can only end the game before the round has started*")
    
  # checks if it is member's turn
  elif member != members_array[int(games[game_id]['turn'])] and started:
    current_turn_name = await client.fetch_user(int(members_array[int(games[game_id]['turn'])]))
    await sender.send(f"*You can't do that because it is currently {current_turn_name.name}'s turn*")

  elif action == 'raise' and started:
    last_raise = int(games[game_id]['last_raise'])
    # check if raise is possible with current money
    member_money = int(bank[member][0])

    if last_raise >= amount:
      await sender.send(f"*Your raise must be greater than the last raise (${last_raise})*")
    elif amount > 0 and member_money - amount >= 0:
      # valid raise
      if member_debt == 0:
        message = f"*{member_name} has raised the bet by ${amount}!*"
      else:
        message = f"*{member_name} has raised the previous raise of ${member_debt} and is the bet is now ${amount}!*"
      for player_index, player in enumerate(members_obj):
        await player.send(message)
        player_debt = int(games[game_id]['members'][str(player.id)]['debt'])
        player_debt += amount
        games[game_id]['members'][str(player.id)]['debt'] = str(player_debt)
      games[game_id]['pot'] = str(curr_pot + amount)
      bank[member][0] = str(member_money - amount)
      games[game_id]['go_to'] = str(prev_turn)
      games[game_id]['last_raise'] = str(amount)
      games[game_id]['members'][member]['debt'] = '0'
      await next_turn()
    elif member_money - amount < 0:
      await sender.send(f"*You don't have enough money to raise by ${amount} (use %bank to see your balance)*")
    elif member_money == 0:
      await sender.send("*You are already all-in. Try using '%game check' instead.*")
    elif amount < 0:
      await sender.send("*You must raise the bet by a value greater than $0*")

  elif action == 'call' and started:
    if member_debt == 0:
      await sender.send("*You have no bet to call*")
    elif member_money == 0:
      await sender.send("*You are already all-in. Try using '%game check' instead.*")
    elif member_money > member_debt:
      games[game_id]['members'][member]['debt'] = '0'
      games[game_id]['pot'] = str(curr_pot + member_debt)
      # subtract from bank
      bank[member][0] = str(member_money - member_debt)
      # send update to players
      for player in members_obj:
        await player.send(f"*{member_name} has called the bet of ${member_debt}*")
      await next_turn()
    else:
      games[game_id]['members'][member]['debt'] = '0'
      games[game_id]['pot'] = str(curr_pot + member_debt)
      bank[member][0] = '0'
      for player in members_obj:
        await player.send(f"*{member_name} has called the bet with ${member_money} and is now all-in!*")
      await next_turn()

  elif action == 'check' and started:
    if member_debt == 0 or member_money == 0:
      for player in members_obj:
        await player.send(f"*{member_name} checked*")
      await next_turn()
    else:
      await sender.send(f"*You must call the ${member_debt} to continue. Use '%game call' to call.*")

  elif action == 'fold' and started:
    for player in members_obj:
      await player.send(f"*{member_name} has folded*")
    games[game_id]['members'][member]['hand'] = []
    games[game_id]['members'][member]['status'] = 'Fold'
    await next_turn()

  # dump new info
  elif not started:
    await sender.send("*Game hasn't started*")
  else:
    await sender.send("*Invalid input*")
  with open("games.json","w") as file:
    json.dump(games, file)
  with open("bank.json","w") as file:
    json.dump(bank, file)


@client.command(brief="Create a poker game")
async def poker(ctx):
  with open("games.json", "r") as file:
    try:
      games = json.load(file)
    except:
      games = dict()

  with open("bank.json", "r") as file:
    try:
      bank = json.load(file)
    except:
      print("There are no members in the bank")
      await ctx.send("**Something went wrong.**")
  
  owner = str(ctx.message.author.id)

  # check if owner is already in a game
  for game in games:
    for member in games[game]['members']:
      if member == owner:
        await ctx.message.author.send(f"**Can't participate in 2 games at once. You are currently in a {games[game]['game']} game.**")
        return
  
  if owner in bank:
    if int(bank[owner][0]) >= 100:
      embed = discord.Embed(title=("POKER: REACT WITH ✅ TO PLAY"), description="People playing: 1", color=discord.Color.blue())
      embed.add_field(name="Players:", value=ctx.message.author.mention, inline=False)
      in_embed = await ctx.send(embed=embed)
      await in_embed.add_reaction("✅")
      denver = pytz.timezone('America/Denver')
      denver_time = datetime.now(denver)
      goal_time = denver_time + timedelta(hours=2)
      goal_string = str(goal_time)
      # write formatted goal to file
      formattedGoal = goal_string[0:19]
      # information about the game
      new_poker = {
        'game': 'poker',
        'community_cards':[],
        'pot': '0',
        'members': {owner: {'status': 'Playing', 'hand': [], 'debt': '0'}},
        'deck': ['021','031','041','051','061','071','081','091','101','111','121','131','141','022','032','042','052','062','072','082','092','102','112','122','132','142','023','033','043','053','063','073','083','093','103','113','123','133','143','024','034','044','054','064','074','084','094','104','114','124','134','144'],
        'start':'0', # index of who started off the round (for big/little blind)
        'turn': '0', # index of whos turn it currently is
        'end_time': formattedGoal, # 2 hours after game is made
        'go_to':'-1',
        'loop_count':'0',
        'last_raise':'0'
      }
      # member info
      games[str(in_embed.id)] = new_poker
      # dump new poker info
      with open("games.json", "w") as file:
        json.dump(games, file)
    else:
      await ctx.send("**You need 100 or more credits to create a poker game.**")
  else:
    await ctx.send("**You dont have money set up! Every hour money is updated and your bank account will be created.**")


@client.command(brief="Returns your total money")
async def bank(ctx):
  with open("bank.json", "r") as file:
    try:
      bank = json.load(file)
    except:
      print("There are no members in the bank")
  member = str(ctx.message.author.id)
  if member not in bank:
    await ctx.send("**You dont have money set up! Every hour money is updated and your bank account will be created.**")
  else:
    await ctx.send(f"**You currently have ${bank[member][0]} in your bank account.**")

@client.event
async def on_raw_reaction_add(payload):
  if str(payload.emoji.name) == "✅" and not payload.member.bot:
    message_id = str(payload.message_id)
    member = str(payload.member.id)
    with open("bank.json", "r") as file:
      try:
        bank = json.load(file)
      except:
        print("There are no members in the bank")
      if member not in bank:
        await payload.member.send("**You can't play because you dont have a bank account set up! Every hour money is updated and your bank account will be created.**")
        return
    with open("games.json", "r") as file:
      games = json.load(file)
    for game in games:
      if game == message_id and member not in games[message_id]['members'] and len(games[message_id]['members']) <= 12:
        # match found
        try:
          in_embed = await client.get_channel(payload.channel_id).fetch_message(int(message_id))
        except:
          print(f"Message for a game could not be found.")
          games.pop(message_id)
          with open("games.json", "w") as file:
            json.dump(games, file)
          return
        send_out = ""
        # create send_out
        player_info = {
          'status': 'Playing',
          'hand': [],
          'debt': '0'
        }
        games[message_id]['members'][member] = player_info
        for member in games[message_id]['members']:
          member_obj = await client.fetch_user(int(member))
          send_out += (member_obj.mention + '\n')
        # embed
        des = "People playing: " + str(len(games[message_id]['members']))
        new_info = discord.Embed(title=("POKER: REACT WITH ✅ TO PLAY"), description=des, color=discord.Color.blue())
        new_info.add_field(name="Players:", value=send_out, inline=False)
        await in_embed.edit(embed=new_info)
        await payload.member.send(f"**You have joined the poker game and you currently have ${bank[member][0]} in your bank account.**")
        # dump new info
        with open("games.json", "w") as file:
          json.dump(games, file)


async def check():
  # update lfg time
  denver = pytz.timezone('America/Denver')
  denver_time = datetime.now(denver)
  formatted_denver = denver_time.strptime(str(denver_time)[0:19], "%Y-%m-%d %H:%M:%S")
  with open("time.json", "r") as file:
    try:
      all_lfg = json.load(file)
    except:
      await asyncio.sleep(60)
      await check()
  #update balances for every player
  new_day = all_lfg["time"]
  extracted_new_day = datetime.strptime(new_day, "%Y-%m-%d %H:%M:%S")
  if (formatted_denver >= extracted_new_day):
    with open("bank.json", "r") as file:
      try:
        bank = json.load(file)
      except:
        print("No players stored in bank")
        bank = dict()
    
    repeat_members = []
    # adds members who are not in bank to bank
    for guild in client.guilds:
      for member in guild.members:
        if str(member.id) not in bank:
          bank[str(member.id)] = ["5000"]
        elif member.id not in repeat_members:
          #add money to existing members
          money = int(bank[str(member.id)][0])
          money += 10
          bank[str(member.id)][0] = str(money)
        repeat_members.append(member.id)
    
    all_lfg["time"] = str(extracted_new_day + timedelta(hours=1))

    with open("time.json", "w") as file:
      json.dump(all_lfg, file)

    with open("bank.json", "w") as file:
      json.dump(bank, file)


keep_alive()
client.run(os.getenv('daKey'))