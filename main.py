from aiogram.utils import executor
from chosen_recipe import dp as dp_chosen
from random_recipe import dp as dp_random

dp = dp_chosen

if __name__ == '__main__':
    try:
        executor.start_polling(dp, skip_updates=True)
    except KeyboardInterrupt:
        print("Bot stopped by user.")
