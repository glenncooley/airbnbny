#!/usr/bin/python3
import configparser
import re
import logging
import argparse
import sys, traceback
import time
import random
#import codecs
#import requests
#from cssselect import HTMLTranslator, SelectorError
import urllib.request
import urllib.parse
from lxml import html
import sqlanydb
import webbrowser
#from PySide import QtGui
#from PySide import QtCore
#from PySide import QtWebKit

#globals
# logging.basicConfig(level=logging.INFO)
logging.basicConfig(format='%(message)s', level=logging.INFO)
conn = sqlanydb.connect(
	userid="DBA",
	password="sql",
	serverName="airbnb",
	databasename="airbnb",
	databasefile="/home/tom/src/airbnb/db/airbnb.db",
)
URL_ROOM_ROOT = "http://www.airbnb.com/rooms/"
URL_HOST_ROOT="https://www.airbnb.com/users/show/"
URL_TIMEOUT=10.0
FILL_MAX_ROOM_COUNT = 50000
SEARCH_MAX_PAGES = 25
SEARCH_MAX_GUESTS = 16
FLAGS_ADD=1
FLAGS_PRINT=9
FLAGS_INSERT_REPLACE=True
FLAGS_INSERT_NO_REPLACE=False

def add_survey(city):
    try:
        cur=conn.cursor()
        cur.execute("call add_survey(?)", (city,))
        sql_identity = """select @@identity"""
        cur.execute(sql_identity, ())
        survey_id = cur.fetchone()[0]
        cur.execute("""
            select survey_id, survey_date, survey_description, search_area_id
            from survey
            where survey_id = ?""",
            (survey_id,))
        (survey_id,
         survey_date,
         survey_description,
         search_area_id ) = cur.fetchone()
        conn.commit()
        cur.close()
        print("Survey added:\n"
                + "\n\tsurvey_id=" + str(survey_id)
                + "\n\tsurvey_date=" + str(survey_date)
                + "\n\tsurvey_description=" + survey_description
                + "\n\tsearch_area_id=" + str(search_area_id))
    except:
        logging.error("Failed to add survey for " + city)
        sys.exit()


def list_surveys():
    try:
        pass
        cur=conn.cursor()
        cur.execute("""
            select survey_id, survey_date, survey_description, search_area_id
            from survey
            order by survey_id asc""")
        result_set = cur.fetchall()
        if len(result_set) > 0:
            template = "| {0:3} | {1:>10} | {2:>30} | {3:3} |"
            print(template.format("ID", "Date", "Description", "SA"))
            for survey in result_set:
                (id, date, desc, sa_id) = survey
                print(template.format(id, date, desc, sa_id))
    except:
        logging.error("Cannot list surveys.")
        sys.exit()

def check_room(room_id):
    try:
        columns = ('room_id', 'host_id', 'room_type', 'country',
                'city', 'neighborhood', 'address', 'reviews',
                'overall_satisfaction', 'accommodates',
                'bedrooms', 'bathrooms', 'price',
                'deleted', 'minstay', 'last_modified', 'latitude',
                'longitude', 'survey_id', )

        sql = "select room_id"
        for column in columns[1:]:
            sql += ", " + column
        sql += " from room where room_id = ?"

        cur = conn.cursor()
        cur.execute(sql, (room_id,))
        result_set = cur.fetchall()
        if len(result_set) > 0:
            for result in result_set:
                i = 0
                print ("Room information: ")
                for column in columns:
                    print ("\t" + column + " = " + str(result[i]))
                    i += 1
            return True
        else:
            print ("\nRoom", str(room_id), "is not in the database.\n")
            return False
        cur.close()
    except:
        traceback.print_exc(file=sys.stdout)
        return False


#class Render(QtWebKit.QWebPage):
class Render():
  def __init__(self, url):
    #checks if QApplication already exists
    self.app=QtGui.QApplication.instance()
    #create QApplication if it doesnt exist
    if not self.app:
        self.app = QtGui.QApplication(sys.argv)
    QtWebKit.QWebPage.__init__(self)
    self.loadFinished.connect(self._loadFinished)
    self.mainFrame().load(QtCore.QUrl(url))
    self.app.exec_()

  def _loadFinished(self, result):
    self.frame = self.mainFrame()
    self.app.quit()


def get_neighborhoods_from_search_area(search_area_id):
    cur=conn.cursor()
    cur.execute("""
        select name
        from neighborhood
        where search_area_id =  ?
        order by name""",
        (search_area_id,))
    neighborhoods = []
    while True:
        row = cur.fetchone()
        if row is None: break
        neighborhoods.append(row[0])
    cur.close()
    return neighborhoods


def display_room(room_id):
    webbrowser.open(URL_ROOM_ROOT + str(room_id))


def display_host(host_id):
    webbrowser.open(URL_HOST_ROOT + str(host_id))


def get_city_info_from_db(search_area_name):
    try:
        # get city_id
        cur = conn.cursor()
        cur.execute("""select search_area_id
		from search_area
		where name = :search_area_name""",
		{"search_area_name": search_area_name})
        search_area_id = cur.fetchone()[0]
        print ("Found search_area " + search_area_name +
		": search_area_id = " + str(search_area_id))

        # get cities
        cur.execute("""select name
                       from city
                       where search_area_id = :search_area_id
                    """,
                        {"search_area_id": search_area_id})
        cities = []
        while True:
            row = cur.fetchone()
            if row is None: break
            cities.append(row[0])

        # get neighborhoods
        cur.execute("""
            select name
            from neighborhood
            where search_area_id =  :search_area_id
            """,
                        {"search_area_id": search_area_id})
        neighborhoods = []
        while True:
            row = cur.fetchone()
            if row is None: break
            neighborhoods.append(row[0])

        cur.close()
        return (cities, neighborhoods)
    except:
        traceback.print_exc(file=sys.stdout)


def get_config(city):
    try:
        # pattern = re.compile(r'.\s+,\s+', re.DOTALL)
        config = ConfigParser.ConfigParser()
        config.read('airbnb.cfg')
        #cities = pattern.split(config.get(city, "cities"))
        cities = list(config.get(city, "cities").split(","))
        cities = [city.lstrip().rstrip() for city in cities]
        neighborhoods = list(config.get(city, "neighborhoods").split(","))
        neighborhoods = [neighborhood.lstrip().rstrip()
                for neighborhood in neighborhoods]
        return (cities, neighborhoods)
    except:
        traceback.print_exc(file=sys.stdout)


def select_room_to_fill():
    try:
        sql = """
                select room_id, survey_id
                from room
                where price is null and deleted != 1
                order by rand()
              """
        cur = conn.cursor()
        cur.execute(sql)
        try:
            (room_id, survey_id) = cur.fetchone()
            cur.close()
            return (room_id, survey_id)
        except TypeError:
            cur.close()
            return None
    except:
        traceback.print_exc(file=sys.stdout)


def save_room_info(room_info, insert_replace_flag):
    try:
        logging.debug("In save_room_info for room " + str(room_info))
        if len(room_info) > 0:
            room_id = int(room_info[0])
            city = room_info[4]
        else:
            room_id = None
            city = None
        deleted = room_info[13]
        cur = conn.cursor()
        try:
            if deleted == 1:
                sql = "update room set deleted = ? where room_id = ?"
                room_id = int(room_info[0])
                cur.execute(sql, (1, room_id,))
            else:
                sql = "insert into room "
                sql += """(
                    room_id,
                    host_id,
                    room_type,
                    country,
                    city,
                    neighborhood,
                    address,
                    reviews,
                    overall_satisfaction,
                    accommodates,
                    bedrooms,
                    bathrooms,
                    price,
                    deleted,
                    minstay,
                    latitude,
                    longitude,
                    survey_id
                    ) """
                if insert_replace_flag: sql += "on existing update defaults on "
                sql += """
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                cur.execute(sql, room_info)
            cur.close()
            conn.commit()
            logging.info("Saved room " + str(room_id))
            return 0
        except sqlanydb.IntegrityError:
            if insert_replace_flag:
                logging.error( "Integrity error: " +  str(room_id))
            else:
                logging.info( "Listing already saved: " +  str(room_id))
                pass # not a problem
            cur.close()
        except ValueError as e:
            logging.error( "room_id = " +  str(room_id) + ": " + e.message)
            cur.close()
            return -1
        except KeyboardInterrupt:
            sys.exit()
        except:
            cur.close()
            traceback.print_exc(file=sys.stdout)
            logging.error("Other error: " +  str(room_id))
            return -1
    except KeyboardInterrupt:
        sys.exit()
    except:
        traceback.print_exc(file=sys.stdout)


def get_page(url):
    # chrome gets the JavaScript-loaded content as well
    # see http://webscraping.com/blog/Scraping-JavaScript-webpages-with-webkit/
    #r = Render(url)
    #page = r.frame.toHtml()
    attempt = 0
    for attempt in range(5):
        try:
            response = urllib.request.urlopen(url, timeout=URL_TIMEOUT)
            page = response.read()
            break
        except KeyboardInterrupt:
            sys.exit()
        except:
            logging.error("Probable connectivity problem retrieving " +
                    url)
            # traceback.print_exc(file=sys.stdout)
            return None
    return page


def get_search_page(url):
    # chrome gets the JavaScript-loaded content as well
    # see http://webscraping.com/blog/Scraping-JavaScript-webpages-with-webkit/
    #r = Render(url)
    #page = r.frame.toHtml()
    try:
        response = urllib.request.urlopen(url, timeout=URL_TIMEOUT)
        page = response.read()
        return page
    except:
        logging.error("Failure retrieving " + url)
        traceback.print_exc(file=sys.stdout)
        return False


def get_room_info(room_id, survey_id, flag):
    try:
        # initialization
        logging.info("Getting info for room " + str(room_id) + " from Airbnb web site")
        room_url = URL_ROOM_ROOT + str(room_id)
        page = get_page(room_url)
        if page is not None:
            get_room_info_from_page(page, room_id, survey_id, flag)
            return True
        else:
            return False
    except KeyboardInterrupt:
        sys.exit()
    except:
        return False


def get_room_info_from_page(page, room_id, survey_id, flag):
    #try:
        #print page
            #except UnicodeEncodeError:
        #if sys.version_info >= (3,):
            #print(page.encode('utf8').decode(sys.stdout.encoding))
        #else:
            #print(page.encode('utf8'))
            #print page.encode('utf8', 'replace')
    try:
        host_id, room_type, country, city, \
        neighborhood, address, reviews, overall_satisfaction,\
        accommodates, bedrooms, bathrooms, price, \
        latitude, longitude, deleted, minstay = \
        None, None, None, None, \
        None, None, None, None, None, None, \
        None, None, None, None, 1, 1
        room_info = (room_id,
                host_id,
                room_type,
                country,
                city,
                neighborhood,
                address,
                reviews,
                overall_satisfaction,
                accommodates,
                bedrooms,
                bathrooms,
                price,
                latitude,
                longitude,
                deleted,
                minstay,
                survey_id
                )
        tree = html.fromstring(page)
        temp = tree.xpath(
            "//div[@id='user']"
            "//a[contains(@href,'/users/show')]"
            "/@href"
        )
        if len(temp) > 0:
            deleted = 0
            host_id_element = temp[0]
            host_id_offset = len('/users/show/')
            host_id = int(host_id_element[host_id_offset:])
        temp = tree.xpath(
            "//table[@id='description_details']"
            "//td[text()[contains(.,'Room type:')]]"
            "/following-sibling::td/text()"
            )
        if len(temp) > 0: room_type = temp[0]
        temp = tree.xpath( "//table[@id='description_details']"
            "//td[text()[contains(.,'Country:')]]"
            "/following-sibling::td/descendant::text()"
            )
        if len(temp) > 0: country = temp[0]
        temp = tree.xpath( "//table[@id='description_details']"
            "//td[text()[contains(.,'City:')]]"
            "/following-sibling::td/descendant::text()"
            )
        if len(temp) > 0: city = temp[0]
        temp = tree.xpath( "//table[@id='description_details']"
            "//td[text()[contains(.,'Neighborhood:')]]"
            "/following-sibling::td/descendant::text()"
            )
        if len(temp) > 0: neighborhood = temp[0]
        temp = tree.xpath(
            "//span[@id='display-address']"
            "/@data-location"
            )
        if len(temp) > 0: address = temp[0]
        temp = tree.xpath(
            "//span[@itemprop='reviewCount']/text()"
            )
        if len(temp) > 0: reviews = temp[0]
        # Now using rating meta tag as overall_satisfaction
        temp = tree.xpath( "//meta"
            "[contains(@property,'airbedandbreakfast:rating')]"
            "/@content"
            )
        if len(temp) > 0: overall_satisfaction = temp[0]
        temp = tree.xpath( "//table[@id='description_details']"
            "//td[text()[contains(.,'Accommodates:')]]"
            "/following-sibling::td/descendant::text()"
            )
        if len(temp) > 0:
            accommodates = temp[0]
            accommodates = accommodates.split('+')[0]
        bedrooms = tree.xpath( "//table[@id='description_details']"
            "//td[text()[contains(.,'Bedrooms:')]]"
            "/following-sibling::td/descendant::text()"
            )
        temp = tree.xpath( "//meta"
            "[contains(@property,'airbedandbreakfast:location:latitude')]"
            "/@content"
            )
        if len(temp) > 0: latitude = temp[0]
        temp = tree.xpath( "//meta"
            "[contains(@property,'airbedandbreakfast:location:longitude')]"
            "/@content"
            )
        if len(temp) > 0: longitude = temp[0]
        if len(bedrooms) > 0:
            bedrooms = bedrooms[0].split('+')[0]
        else:
            bedrooms = None
        bathrooms = tree.xpath( "//table[@id='description_details']"
            "//td[text()[contains(.,'Bathrooms:')]]"
            "/following-sibling::td/descendant::text()"
            )
        if len(bathrooms) > 0:
            bathrooms = bathrooms[0].split('+')[0]
        else:
            bathrooms = None
        temp = tree.xpath( "//table[@id='description_details']"
            "//td[text()[contains(.,'Minimum Stay:')]]"
            "/following-sibling::td/descendant::text()"
            )
        if len(temp) > 0:
            minstay = temp[0]
            non_decimal = re.compile(r'[^\d.]+')
            minstay = non_decimal.sub('', minstay)
        else:
            minstay = "1"
        temp = tree.xpath( "//div[@id='price_amount']/text()")
        if len(temp) > 0:
            price = temp[0][1:]
            non_decimal = re.compile(r'[^\d.]+')
            price = non_decimal.sub('', price)
        room_info = (
            room_id,
            host_id,
            room_type,
            country,
            city,
            neighborhood,
            address,
            reviews,
            overall_satisfaction,
            accommodates,
            bedrooms,
            bathrooms,
            price,
            deleted,
            minstay,
            latitude,
            longitude,
            survey_id
            )
        if flag==FLAGS_ADD:
            save_room_info(room_info, FLAGS_INSERT_REPLACE)
        elif flag==FLAGS_PRINT:
            print ("Room info:")
            print ("\troom_id:", str(room_id))
            print ("\thost_id:", str(host_id))
            print ("\troom_type:", room_type)
            print ("\tcountry:", country)
            print ("\tcity:", city)
            print ("\tneighborhood:", neighborhood)
            print ("\taddress:", address)
            print ("\treviews:", reviews)
            print ("\toverall_satisfaction:", overall_satisfaction)
            print ("\taccommodates:", accommodates)
            print ("\tbedrooms:", bedrooms)
            print ("\tbathrooms:", bathrooms)
            print ("\tprice:", price)
            print ("\tdeleted:", deleted)
            print ("\tlatitude:", str(latitude))
            print ("\tlongitude:", str(longitude))
            print ("\tminstay:", minstay)
        return True
    except KeyboardInterrupt:
        sys.exit()
    except IndexError:
        logging.error( "Web page has unexpected structure.")
        traceback.print_exc(file=sys.stdout)
        return False
    except:
        traceback.print_exc(file=sys.stdout)
        return False


def fill_loop_by_room():
    room_count = 0
    #if len(argv) > 1:
        #get_room_info(int(argv[1]))
        #room_count += 1
    while room_count < FILL_MAX_ROOM_COUNT:
        (room_id, survey_id) = select_room_to_fill()
        if room_id is None:
            break
        else:
            time.sleep(3.0 * random.random())
            if(get_room_info(room_id, survey_id, FLAGS_ADD)):
                room_count += 1


def get_search_area_from_survey_id(survey_id):
    cur = conn.cursor()
    cur.execute("""
        select sa.search_area_id, sa.name
        from search_area sa join survey s
        on sa.search_area_id = s.search_area_id
        where s.survey_id = ?""", (survey_id,))
    try:
        (search_area_id, name) = cur.fetchone()
        cur.close()
        return (search_area_id, name)
    except KeyboardInterrupt:
        cur.close()
        sys.exit()
    except:
        cur.close()
        return None


def page_has_been_retrieved(survey_id, room_type, neighborhood, guests,
        page_number):
    """
    Returns 1 if the page has been retrieved and has rooms
    Returns 0 if the page has been retrieved and has no rooms
    Returns -1 if the page has not been retrieved
    """
    cur = conn.cursor()
    count = 0
    try:
        sql = """
            select ssp.has_rooms
            from survey_search_page ssp
            join neighborhood nb
            on ssp.neighborhood_id = nb.neighborhood_id
            where survey_id = ?
            and room_type = ?
            and nb.name = ?
            and guests = ?
            and page_number = ?"""
        cur.execute(sql, (survey_id, room_type, neighborhood, guests, page_number))
        count = cur.fetchone()[0]
        logging.debug("count = " + str(count))
    except:
        count = -1
        logging.debug("page has not been retrieved")
    finally:
        cur.close()
        return count



def save_survey_search_page(survey_id, room_type, neighborhood_id,
    guests, page_number, has_rooms):
    try:
        sql = """
        insert into survey_search_page(survey_id, room_type, neighborhood_id,
        guests, page_number, has_rooms)
        values (?, ?, ?, ?, ?, ?)
        """
        cur = conn.cursor()
        cur.execute(sql, (survey_id, room_type, neighborhood_id, guests,
            page_number, has_rooms))
        cur.close()
        conn.commit()
        return True
    except:
        logging.error("Save survey search page failed")
        return False




def get_neighborhood_id(survey_id, neighborhood):
    sql = """
    select neighborhood_id
    from neighborhood nb
        join search_area sa
        join survey s
    on nb.search_area_id = sa.search_area_id
    and sa.search_area_id = s.search_area_id
    where s.survey_id = ?
    and nb.name = ?
    """
    cur = conn.cursor()
    cur.execute(sql, (survey_id, neighborhood, ))
    neighborhood_id = cur.fetchone()[0]
    cur.close()
    return neighborhood_id

def searcher(survey_id):
    try:
        (search_area_id, name) = get_search_area_from_survey_id(survey_id)
        neighborhoods = get_neighborhoods_from_search_area(search_area_id)

        for room_type in (
                "Private room",
                "Entire home/apt",
                "Shared room",
                ):
            if name=="san_francisco":
                url_root = "https://www.airbnb.com/s/San-Francisco"
            elif name=="new_york":
                url_root = "https://www.airbnb.com/s/New-York--NY"
            else:
                url_root = "https://www.airbnb.com/s/" + name
            for neighborhood in neighborhoods:
                if room_type in ("Private room", "Shared room"):
                    max_guests = 4
                else:
                    max_guests = SEARCH_MAX_GUESTS
                for guests in range(1,max_guests):
                    for page_number in range(1,SEARCH_MAX_PAGES):
                        logging.info(
                                room_type + ", " +
                                neighborhood + ", " +
                                str(guests) + " guests, " +
                                "page " + str(page_number)
                            )
                        count = page_has_been_retrieved(
                            survey_id, room_type,
                            neighborhood, guests, page_number)
                        if count == 1:
                            logging.debug("\t...page already visited")
                            continue
                        if count == 0:
                            logging.debug("\t...page already visited")
                            break

                        url_suffix = "guests=" + str(guests)
                        url_suffix += "&"
                        url_suffix += urllib.parse.quote("neighborhoods[]")
                        url_suffix += "="
                        # Rome: Unicode wording, equal comparison failed
                        # to convert both args to unicode (prob url_suffix
                        # and urllib2.quote(neighborhood)
                        url_suffix += urllib.parse.quote(neighborhood)
                        url_suffix += "&"
                        url_suffix += urllib.parse.quote("room_types[]")
                        url_suffix += "="
                        url_suffix += urllib.parse.quote(room_type)
                        url_suffix += "&"
                        url_suffix += "page=" + str(page_number)
                        url = url_root + "?" + url_suffix
                        logging.debug("URL: " + url)
                        time.sleep(3.0 * random.random())
                        page = get_search_page(url)
                        if page is False: break
                        tree = html.fromstring(page)
                        room_elements = tree.xpath(
                            "//div[@class='listing']/@data-id"
                        )
                        neighborhood_id = get_neighborhood_id(
                            survey_id, neighborhood)
                        if len(room_elements) > 0:
                            has_rooms = 1
                        else:
                            has_rooms = 0
                        save_survey_search_page(survey_id,
                            room_type, neighborhood_id,
                            guests, page_number, has_rooms, )
                        if has_rooms:
                            logging.debug(str(room_elements[0]))
                            for room_element in room_elements:
                                #room_id = room_element.get('data-hosting-id')
                                room_id = int(room_element)
                                room_info = (
                                    room_id,
                                    None, # host_id,
                                    None, # room_type,
                                    None, # country,
                                    None, # city,
                                    None, # neighborhood,
                                    None, # address,
                                    None, # reviews,
                                    None, # overall_satisfaction
                                    None, # accommodates
                                    None, # bedrooms
                                    None, # bathrooms
                                    None, # price
                                    0, # deleted
                                    None, # minstay
                                    None, # latitude
                                    None, # longitude
                                    survey_id, #survey_id
                                    )
                                if room_id is not None:
                                    save_room_info(
                                            room_info, FLAGS_INSERT_NO_REPLACE)
                        else:
                            logging.info("No rooms found")
                            break
    except KeyboardInterrupt:
        sys.exit()
    except:
        traceback.print_exc(file=sys.stdout)

def get_city_info_from_web_site(city):
    try:
        url = "https://www.airbnb.com/s/" + city
        page = get_search_page(url)
        if page is False:
            return False
        tree = html.fromstring(page)
        cur = conn.cursor()
        try:
            citylist = tree.xpath(
                    "//input[@name='location']/@value"
                    )
            if len(citylist) > 0:
                # check if it exists
                sql_check = """
                    select name
                    from search_area
                    where name = ?"""
                cur.execute(sql_check, (citylist[0],))
                if cur.fetchone() is not None:
                    logging.info("City already exists: " + citylist[0])
                    return
                sql_search_area = """insert
                            into search_area (name)
                            values (?)"""
                cur.execute(sql_search_area, (citylist[0],))
                #city_id = cur.lastrowid
                sql_identity = """select @@identity"""
                cur.execute(sql_identity, ())
                search_area_id = cur.fetchone()[0]
                sql_city = """insert
                        into city (name, search_area_id)
                        on existing skip
                        values (?,?)"""
                print (city, str(search_area_id))
                cur.execute(sql_city, (city, search_area_id,))
                logging.info("Added city " + city)
            neighborhoods = tree.xpath(
                        "//input[@name='neighborhood']/@value"
                    )
            if len(neighborhoods) > 0:
                sql_neighborhood = """insert
                    into neighborhood(name, search_area_id)
                    on existing skip
                    values(?, ?)
                    """
                for neighborhood in neighborhoods:
                    cur.execute(sql_neighborhood,
                            (neighborhood, search_area_id,))
                    logging.info("Added neighborhood " + neighborhood)
            else:
                logging.info("No neighborhoods found for " + city)
            conn.commit()
        except UnicodeEncodeError:
            if sys.version_info >= (3,):
                print(s.encode('utf8').decode(sys.stdout.encoding))
            else:
                print(s.encode('utf8'))
        except:
            traceback.print_exc(file=sys.stdout)
            logging.error("Error collecting city and neighborhood information")
    except:
        traceback.print_exc(file=sys.stdout)


def main():
    parser = argparse.ArgumentParser(
            description='Manage a database of Airbnb listings.',
            usage='%(prog)s [options]')
    parser.add_argument('-ac', '--addcity',
            metavar='city', action='store', default=False,
            help='get and save the name and neighborhoods for search area (city)')
    parser.add_argument('-ar', '--addroom',
            metavar='room_id', action='store', default=False,
            help='add a room_id to the database')
    parser.add_argument('-as', '--addsurvey',
            metavar='city', type = str,
            help='add a survey entry to the database, for city')
    parser.add_argument('-dh', '--displayhost',
            metavar='host_id', type=int,
            help='display web page for host_id in browser')
    parser.add_argument('-dr', '--displayroom',
            metavar='room_id', type=int,
            help='display web page for room_id in browser')
    parser.add_argument('-f', '--fill',
            action='store_true', default=False,
            help='fill in details for room_ids collected with -s')
    parser.add_argument('-kr', '--check',
            metavar='room_id', type=int,
            help='check if room_id is in the database')
    parser.add_argument('-ls', '--listsurveys',
            action='store_true', default=False,
            help='list the surveys in the database')
    parser.add_argument('-pr', '--printroom',
            metavar='room_id', type=int,
            help='print room_id information from the Airbnb web site')
    parser.add_argument('-ps', '--printsurvey',
            metavar='survey_id', type=int,
            help='print survey information for survey_id')
    parser.add_argument('-s', '--search',
            metavar='survey_id', type=int,
            help='search for rooms using survey survey_id')
    args = parser.parse_args()

    try:
        if args.search:
            searcher(args.search)
        elif args.fill:
            fill_loop_by_room()
        elif args.check:
            check_room(args.check)
        elif args.addroom:
            get_room_info(int(args.addroom), None, FLAGS_ADD)
        elif args.addcity:
            get_city_info_from_web_site(args.addcity)
        elif args.addsurvey:
            add_survey(args.addsurvey)
        elif args.displayhost:
            display_host(args.displayhost)
        elif args.displayroom:
            display_room(args.displayroom)
        elif args.listsurveys:
            list_surveys()
        elif args.printroom:
            get_room_info(args.printroom, None, FLAGS_PRINT)
        else:
            print ("Use -h for usage")

    except:
        traceback.print_exc(file=sys.stdout)

if __name__ == "__main__":
    main()
