# -*- coding: utf-8 -*-
###
# Copyright (c) 2011, Nicolas Paris
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

###

import supybot.utils as utils
import supybot.ircmsgs as ircmsgs
from supybot.commands import *
import supybot.plugins as plugins
import supybot.schedule as schedule
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks

import os
import csv
import time
import random

CHANNEL = '#salon'
MAX_LETTERS = 9
LAPS_TIME = 30

class Scrabble(callbacks.Plugin):
    """Add the help for "@plugin help Scrabble" here
    This should describe *how* to use this plugin."""
    threaded = True

    def __init__(self, irc):
        self.__parent = super(Scrabble, self)
        self.__parent.__init__(irc)
        self.started = False
        random.seed()
        self.task = 0
        self.no_answer = 0
        # We want all 100 letters available in a real scrabble game (without
        # blanks)
        self.letters = 'E' *15 + 'A' *9 + 'I' *8 + 'N' *6 + 'O' *6 + 'R' *6 + \
            'S' *6 + 'T' *6 + 'U' *6 + 'L' *5 + 'D' *3 + 'M' *3 + 'G' *2 + 'B' *2 + \
            'C' *2 + 'P' *2 + 'F' *2 + 'H' *2 + 'V' *2 + 'J' *1 + 'Q' *1  + 'K' *1\
            + 'W' *1 + 'X' *1 + 'Y' *1 + 'Z' *1

        # The score of each letters (as seen in wikipedia page)
        self.letters_score = {
            'A':1, 'E':1, 'I':1, 'N':1, 'O':1, 'R':1, 'S':1, 'T':1, 'U':1, 'L':1,
            'D':2, 'G':2, 'M':2, 'B':3, 'C':3, 'P':3, 'F':4, 'H':4, 'V':4,
            'J':8, 'Q':8, 'K':10, 'W':10, 'X':10, 'Y':10, 'Z':10,
        }
        self._init_tries()

    def _init_tries(self):
        self.tries = {
            'score': 0,
            'nick': '',
            'word': '',
        }

    def doPrivmsg (self, irc, msg):
        if self.started and msg.args[0] == '#testalacon'\
            and len(msg.args[1].split(' ')) is 1:
            word = msg.args[1].upper()
            if self._is_valid_word(word):
                score = self._count_points(word)
                if score > self.tries['score']:
                    self._update_tries(word, msg)
                    irc.queueMsg(ircmsgs.privmsg(CHANNEL, 
                        'Le mot %s rapporte %s points' % (word, str(score))))

    def start (self, irc, msg, args):
        if self.started:
            return
        self._parse_dictionnary(irc)
        self.started = True
        self._run_game(irc)

    start = wrap (start)

    def stop (self, irc, msg, args):
        self.started = False
        irc.queueMsg(ircmsgs.privmsg(CHANNEL, 'Jeu Stoppé'))

    stop = wrap(stop)

    def what (self, irc, msg, args):
        self._display_hand(irc)

    what = wrap(what)

    def next (self, irc, msg, args):
        self._run_game(irc)

    def _update_tries (self, word, msg):
        self.tries['score'] = self._count_points(word)
        self.tries['nick'] = msg.nick
        self.tries['word'] = word


    def _run_game (self, irc):
        if self.task != 0:
            schedule.removeEvent(self.task)
            self.task = 0

        if self.no_answer is 3:
            self.started = False
            irc.queueMsg(ircmsgs.privmsg(CHANNEL, 'Jeu Stoppé'))
            return

        if self.started:
            if self.tries['score'] != 0:
                self.no_answer = 0
                self._display_best_try(irc)
                self._best_word(irc)
                self._display_top(irc)
                self._update_score_db()
                self._init_tries()
            else:
                self.no_answer += 1
            self._choose_letters(irc)

        def f():
            self.task = 0
            self._run_game (irc)
        if self.started:
            self.task = schedule.addEvent(f, time.time() + LAPS_TIME)

    def _display_best_try (self, irc):
        irc.queueMsg(ircmsgs.privmsg(CHANNEL, 
            'Bravo %s, le mot %s te rapporte %s points' % (
            self.tries['nick'], self.tries['word'], self.tries['score']    
        )))

    def _update_score_db (self):
        db_file = 'plugins/Scrabble/scores.db'
        data = []
        i = 0
        try:
            if os.path.isfile(db_file):
                with open(db_file, 'r') as f:
                    match = False
                    reader = csv.reader(f)
                    for item in reader:
                        i += 1
                        if self.tries['nick'] in item:
                            item[1] = int(item[1]) + self.tries['score']
                            match = True
                        data.append(item)
                    if not match:
                        data.append([self.tries['nick'], self.tries['score']])
        except IOError:
            return

        with open(db_file, 'w') as f:
            writer = csv.writer(f)
            if i is 0:
                writer.writerow([self.tries['nick'], self.tries['score']])
            elif i is 1:
                writer.writerow(data[0])
            else:
                writer.writerows(data)

    def _display_top (self, irc):
        db_file = 'plugins/Scrabble/scores.db'
        data = []
        try:
            if os.path.isfile(db_file):
                with open(db_file, 'r') as f:
                    reader = csv.reader(f)
                    for item in reader:
                        data.append([int(item[1]), item[0]])
        except IOError:
            return
        data.sort()
        message = 'Le top 5 est: '
        for i in range(5):
            try:
                score, nick = data.pop()
                message += '%s (%s), ' % (nick, score)
            except:
                pass
        irc.queueMsg(ircmsgs.privmsg(CHANNEL, message))


    def _parse_dictionnary (self, irc):
        self.words = []
        with open('plugins/Scrabble/ODS5.txt') as f:
            for word in f:
                if word is not '':
                    self.words.append(word.strip())
        irc.reply('Jeu démarré, %s mots dans le dictionnaire' % str(len(self.words)))

    def _is_valid_word (self, word):
        for letter in word:
            if word.count(letter) > self.hand.count(letter):
                return False
            if word not in self.words:
                return False
        return True

    def _count_points (self, word):
        score = 0
        if len(word) is MAX_LETTERS:
            score += 50
        for l in word:
            score += self.letters_score[l]
        return score

    def _choose_letters (self, irc):
        self.hand = random.sample(self.letters, MAX_LETTERS)
        self._display_hand(irc)

    def _display_hand (self, irc):
        display_hand = ''
        for l  in self.hand:
            display_hand += '%s ' % l
        irc.queueMsg(ircmsgs.privmsg(CHANNEL, 'Lettres selectionnées: %s' % display_hand))

    def _best_word (self, irc):
        max_score = 0
        best_word = ''
        for word in self.words:
            w = list(word)
            h = list(self.hand)
            try:
                for i in w:
                    h.remove(w.pop())
                score = self._count_points(word)
                if score > max_score:
                    max_score = score
                    best_word = word
            except:
                pass

        irc.queueMsg(ircmsgs.privmsg(CHANNEL, 
                    'Meilleur mot trouvé: %s, %s points' % (best_word, max_score)))


        
Class = Scrabble

# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
