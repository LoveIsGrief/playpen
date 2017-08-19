"""

Variables prefixed with "t_" are related to TMDB and "i_" is related to imdb
  Hey, we get lazy sometimes
"""
import argparse
import csv
import json

import os
import tmdbsimple as tmdb
from configparser import ConfigParser

LIST_FAVORITE = "favorite"
LIST_WATCHLIST = "watchlist"
LIST_RATED = "rated"

__author__ = "LoveIsGrief"

CONFIG_FILENAME = "tmdb.ini"
KEYS_SECTION = "keys"
CLIENT_SECTION = "client"
TOKENS_SECTION = "tokens"

IMDB_TYPE_TV = "TV Series"
TMDB_TYPE_MOVIE = "movie"
TMDB_TYPE_TV = "tv"

TMDB_MEDIA_CACHE_NAME = "imdb_to_tmdb_media.json"


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
        TMDB_TYPE_TV: {
            LIST_FAVORITE: [],
            LIST_WATCHLIST: [],
            LIST_RATED: [],
        },
        TMDB_TYPE_MOVIE: {
            LIST_FAVORITE: [],
            LIST_WATCHLIST: [],
            LIST_RATED: [],
        },

    }
    for item in vid_list:
        # TODO add method to guess media_type
        # missing: "TV Movie", "Mini-Series"
        media_dict = ret[TMDB_TYPE_TV] if item["title type"] == IMDB_TYPE_TV else ret[TMDB_TYPE_MOVIE]
        rating = str2int(item.get("you rated"))
        if rating:
            if rating >= favorite_threshold:
                media_dict[LIST_FAVORITE].append(item)
            media_dict[LIST_RATED].append(item)
        else:
            media_dict[LIST_WATCHLIST].append(item)
    return ret


def imdb_2_tmdb_item(item, media_type):
    # A cache to make sure we don't make too many requests to tmdb
    cache = {}
    if os.path.exists(TMDB_MEDIA_CACHE_NAME):
        with open(TMDB_MEDIA_CACHE_NAME, 'r') as cache_file:
            cache = json.load(cache_file)
    i_id = item["const"]
    ret = cache.get(i_id)
    if ret:
        return ret

    find = tmdb.Find(i_id)
    ret = next(iter(
        find.info(external_source="imdb_id").get("%s_results" % media_type, [])
    ), None)
    if ret is not None:
        with open(TMDB_MEDIA_CACHE_NAME, 'w') as cache_file:
            cache[i_id] = ret
            json.dump(cache, cache_file, indent=2)
    return ret


def get_account_pages(func, current_page=1):
    """
    Calls a paged API until all results have been retrieved

    :param func:
    :type func: callable
    :return: key:id, value: t_media
    :rtype: dict
    """
    api_ret = func(page=current_page)
    ret = tmdb_results_to_dict(api_ret["results"])
    ret_page = api_ret["page"]
    if ret_page < api_ret["total_pages"]:
        ret.update(get_account_pages(func, ret_page + 1))
    return ret


def tmdb_results_to_dict(results):
    """
    key: tmdb id, value: tmdb item

    :param results: List of
                        - https://developers.themoviedb.org/3/movies
                        - https://developers.themoviedb.org/3/tv
    :type results: list[dict]
    :return:
    :rtype:
    """
    return {result["id"]: result for result in results}


def main(session_id, favorite_threshold, csv_path):
    vid_list = build_imdb_vid_list(csv_path)

    # Sort movies into their respective lists
    sorted_vid_list = sort_vid_list(vid_list, favorite_threshold)

    account = tmdb.Account(session_id)
    acc_info = account.info()

    # Prepare for making requests for the user account
    tmdb.id = acc_info["id"]

    # Similar to sorted_vid_list, but with dicts for faster comparisons
    # key: id, value: t_dict
    account_vid_list = {
        TMDB_TYPE_MOVIE: {
            LIST_FAVORITE: get_account_pages(account.favorite_movies),
            LIST_WATCHLIST: get_account_pages(account.watchlist_movies),
            LIST_RATED: get_account_pages(account.rated_movies),
        },
        TMDB_TYPE_TV: {
            LIST_FAVORITE: get_account_pages(account.favorite_tv),
            LIST_WATCHLIST: get_account_pages(account.watchlist_tv),
            LIST_RATED: get_account_pages(account.rated_tv),
        }
    }

    for media_type in [TMDB_TYPE_MOVIE, TMDB_TYPE_TV]:
        vid_dict = sorted_vid_list[media_type]
        account_vid_dict = account_vid_list[media_type]

        # Add stuff to favorites, watchlist and rated
        for t_list_type in [LIST_FAVORITE, LIST_RATED, LIST_WATCHLIST]:
            for i_vid in vid_dict[t_list_type]:
                t_vid = imdb_2_tmdb_item(i_vid, media_type)
                if t_vid is None:
                    print("Couldn't find '%s' %s %s" % (i_vid["title"], i_vid["title type"], i_vid["url"]))
                    continue

                t_vid_id = t_vid["id"]
                if t_vid_id in account_vid_dict[t_list_type]:
                    print("Old %s: %s" % (t_list_type, i_vid["title"]))
                    continue

                # Rate or add to favorites/watchlist
                if t_list_type == LIST_RATED:
                    if media_type == TMDB_TYPE_MOVIE:
                        medium_class = tmdb.Movies
                    else:
                        medium_class = tmdb.TV
                    func = medium_class(t_vid_id).rating
                    kwargs = {
                        "session_id": session_id,
                        "value": i_vid["you rated"]
                    }
                else:
                    func = getattr(account, t_list_type)
                    kwargs = {
                        "media_type": media_type,
                        "media_id": t_vid_id,
                        t_list_type: True
                    }
                func(**kwargs)
                print("New %s: %s" % (t_list_type, i_vid["title"]))


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
