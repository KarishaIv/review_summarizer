import os
import re
import ssl
import urllib

import pymorphy2
import requests
from http.cookiejar import CookieJar
from urllib.parse import urlparse, parse_qs, quote
import urllib.request
import certifi
from bs4 import BeautifulSoup

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types
from aiogram.utils.exceptions import InvalidQueryID
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext

from messages import WELCOME_MESSAGE

from aiogram.utils import executor
from chosen_recipe import dp as dp_chosen
from random_recipe import dp as dp_random

import json
import requests
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from aiogram import types
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message, Chat, User
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.exceptions import InvalidQueryID
