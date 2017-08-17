"""
TODO should use https://github.com/celiao/tmdbsimple/
TODO pip install tmdbsimple
"""
import argparse
import csv
import tmdbsimple as tmdb
from configparser import ConfigParser

__author__ = "LoveIsGrief"

CONFIG_FILENAME = "tmdb.ini"
KEYS_SECTION = "keys"
CLIENT_SECTION = "client"
TOKENS_SECTION = "tokens"
TYPE_TV = "TV Series"


def str2int(string):
    try:
        return int(string)
    except:
        return None


def build_imdb_vid_list(csv_path):
    """
    Interpret a CSV
    :param csv_path:
    :type csv_path: str
    :return:
    :rtype: list[dict]
    """
    with open(csv_path) as csvfile:
        csv_reader = csv.reader(csvfile)
        fieldnames = next(csv_reader)

        return [{fieldname.lower(): row[idx] for idx, fieldname in enumerate(fieldnames)}
                for row in csv_reader]


def sort_vid_list(vid_list, favorite_threshold):
    ret = {
        "tv": {
            "favorites": [],
            "watchlist": [],
            "rated": [],
        },
        "movies": {
            "favorites": [],
            "watchlist": [],
            "rated": [],
        },

    }
    for item in vid_list:
        type_dict = ret["tv"] if item["title type"] == TYPE_TV else ret["movies"]
        rating = str2int(item.get("you rated"))
        if rating:
            if rating >= favorite_threshold:
                type_dict["favorites"].append(item)
            type_dict["rated"].append(item)
        else:
            type_dict["watchlist"].append(item)
    return ret


def imdb_2_tmdb_item(item):
    find = tmdb.Find(item["const"])
    return find.info(external_source="imdb_id")


def main(session_id, favorite_threshold, csv_path):
    vid_list = build_imdb_vid_list(csv_path)

    # Sort movies into their respective lists
    sorted_vid_list = sort_vid_list(vid_list, favorite_threshold)
    movies = sorted_vid_list["movies"]
    tv_series = sorted_vid_list["tv"]

    account = tmdb.Account(session_id)
    acc_info = account.info()

    # Prepare for making requests for the user account
    tmdb.id = acc_info["id"]

    # Add stuff to favorites
    # TODO: add movie to watchlist or favorites
    for movie in movies["favorites"]:
        item = imdb_2_tmdb_item(movie)["movie_results"][0]
        account.favorite(media_type="movie", media_id=item["id"], favorite=True)

        # TODO decide if we need to check the favorite and watch lists in order to make less requests
        # favorite_movies = account.favorite_movies()["results"]
        # favorite_tv = account.favorite_tv()["results"]
        # watchlist_movies = account.watchlist_movies()["results"]
        # watchlist_tv = account.watchlist_tv()["results"]


def request_new_token(config):
    auth = tmdb.Authentication()
    token_dict = auth.token_new()
    request_token = token_dict["request_token"]
    authorization_url = " https://www.themoviedb.org/authenticate/%s" % request_token

    input("Please authorize this app using the url %s\n" % authorization_url)
    session_dict = auth.session_new(request_token=request_token)

    config.set(TOKENS_SECTION, "session", session_dict["session_id"])
    with open(CONFIG_FILENAME, "w") as config_file:
        config.write(config_file)
    print("Updated config for future use")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Imports exported movie/serie lists in CSV format from the IMDB into The Movie DB"
    )
    parser.add_argument(
        "-f", "--favorite",
        type=int,
        choices=list(range(0, 11)),
        default=8,
        help="Minimum rating for adding to favorites",
        required=False
    )
    parser.add_argument(
        "csv",
        help="Location of the csv file"
    )

    args = parser.parse_args()

    # If you already have an access/refresh pair in hand
    config = ConfigParser()
    config.read(CONFIG_FILENAME)

    try:
        tmdb.API_KEY = config.get(KEYS_SECTION, "api")
    except:
        print("Please add an 'api' key to the %s section of the configuration" % KEYS_SECTION)
        exit(1)

    if TOKENS_SECTION in config and "session" in config[TOKENS_SECTION]:
        main(config.get(TOKENS_SECTION, "session"), args.favorite, args.csv)
    else:
        if TOKENS_SECTION not in config:
            config.add_section(TOKENS_SECTION)
        request_new_token(config)
        main(config.get(TOKENS_SECTION, "session"), args.favorite, args.csv)
