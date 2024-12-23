from imports import *

dp = dp_chosen

if __name__ == '__main__':
    try:
        executor.start_polling(dp, skip_updates=True)
    except KeyboardInterrupt:
        print("Bot stopped by user.")
