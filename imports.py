import os
import re
import ssl
import json
import urllib
import requests
from http.cookiejar import CookieJar
from urllib.parse import urlparse, parse_qs, quote
import urllib.request
import certifi

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.utils.exceptions import InvalidQueryID
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext

from messages import WELCOME_MESSAGE
