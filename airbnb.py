import codecs
import re
import logging
import argparse
import sys, traceback
import urllib2
import requests
from lxml import html
from cssselect import HTMLTranslator, SelectorError
import sqlite3
from PySide import QtGui
from PySide import QtCore
from PySide import QtWebKit

#globals
#logging.basicConfig(filename='airbnb.log',level=logging.DEBUG)
logging.basicConfig(format='%(message)s',
        level=logging.INFO)
conn = sqlite3.connect('airbnb.db3')
ROOT_URL = "http://www.airbnb.com/rooms/"
MAX_ROOM_COUNT = 5700
cities_ny =  (
"Bronx",
"Brooklyn",
"Jamaica",
"Jersey City",
"Long Island City",
"Manhattan, New York",
"Queens",
"Staten Island",
"West New York",
"New York",
"Union City"
)
neighborhoods_ny =  (
 "Alphabet City",
 "Astoria",
 "Battery Park City",
 "Bay Ridge",
 "Bayside",
 "Bedford-Stuyvesant",
 "Bensonhurst",
 "Bergen Beach",
 "Boerum Hill",
 "Brighton Beach",
 "Brooklyn Heights",
 "Brooklyn Navy Yard",
 "Bushwick",
 "Canarsie",
 "Carroll Gardens",
 "Chelsea",
 "Chinatown",
 "Civic Center",
 "Claremont",
 "Clinton Hill",
 "Cobble Hill",
 "Columbia Street Waterfront",
 "Concourse",
 "Coney Island",
 "Crown Heights",
 "DUMBO",
 "Ditmars / Steinway",
 "Downtown Brooklyn",
 "East Flatbush",
 "East Harlem",
 "East New York",
 "East Village",
 "Financial District",
 "Flatbush",
 "Flatiron District",
 "Flushing",
 "Forest Hills",
 "Fort Greene",
 "Gerritsen Beach",
 "Gowanus",
 "Gramercy Park",
 "Greenpoint",
 "Greenwich Village",
 "Greenwood Heights",
 "Hamilton Heights",
 "Harlem",
 "Hell's Kitchen",
 "Hudson Square",
 "Inwood",
 "Jackson Heights",
 "Jamaica",
 "Kensington",
 "Kips Bay",
 "Lefferts Garden",
 "Little Italy",
 "Long Island City",
 "Lower East Side",
 "Manhattan Beach",
 "Meatpacking District",
 "Midland Beach",
 "Midtown East",
 "Midwood",
 "Morningside Heights",
 "Mott Haven",
 "Murray Hill",
 "Noho",
 "Nolita",
 "Park Slope",
 "Prospect Heights",
 "Queens",
 "Red Hook",
 "Rego Park",
 "Richmond Hill",
 "Ridgewood",
 "Riverdale",
 "Roosevelt Island",
 "Sheepshead Bay",
 "Soho",
 "South Beach",
 "South Street",
 "Seaport",
 "St. George",
 "Staten Island",
 "Sunnyside",
 "Sunset Park",
 "The Bronx",
 "The Rockaways",
 "Times Square/Theatre District",
 "Tribeca",
 "Union Square",
 "Upper East Side",
 "Upper West Side",
 "Washington Heights",
 "West Brighton",
 "West Village",
 "Williamsburg",
 "Windsor Terrace",
 "Woodside",
)
# neighborhoods_ny = ("X")

def check_room(room_id):
    try:
        sql = """
                select *
                from room
                where room_id = ?
              """
        cur = conn.cursor()
        cur.execute(sql, (room_id,))
        try:
            room_info = cur.fetchone()[0]
            logging.debug("room_info" + room_info)
            return True
        except TypeError:
            return False
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

def create_table():
    try:
        sql = """CREATE TABLE room (
        room_id integer primary key,
        host_id integer,
        room_type string,
        country string,
        city string,
        neighborhood string,
        address string,
        reviews int,
        overall_satisfaction float,
        active int,
        accommodates int,
        bedrooms int,
        bathrooms int,
        price float,
        deleted int,
        minstay int
        )
        """
        conn.execute(sql)
    except sqlite3.OperationalError:
        pass
    except:
        traceback.print_exc(file=sys.stdout)

def select_room():
    try:
        sql = """
                select room_id
                from room
                where minstay is null
                and active = 1
                order by random()
              """
        cur = conn.cursor()
        cur.execute(sql)
        try:
            room_id = cur.fetchone()[0]
            return room_id
        except TypeError:
            return None
    except:
        traceback.print_exc(file=sys.stdout)

def save_room_info(room_info, replace_flag):
    try:
        if len(room_info) > 0:
            room_id = int(room_info[0])
            city = room_info[4]
        else:
            room_id = None
            city = None
        if (city is not None) & (city not in cities_ny):
            active = 0
        else:
            active = 1
        room_info += (active,)
        sql = "insert "
        if replace_flag: sql += "or replace "
        sql += """into room (
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
            active
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            conn.execute(sql, room_info)
            conn.commit()
            if active == 0:
                logging.info("Deactivated room " + str(room_id) + " in " + city)
            else:
                logging.info("Saved room " + str(room_id) + " in " + city)
            return (active - 1)
        except ValueError:
            logging.error( "Value error: " +  str(room_id))
            return -1
        except sqlite3.IntegrityError:
            if replace_flag:
                logging.error( "Integrity error: " +  str(room_id))
            else:
                pass # not a problem
            return -1
        except:
            logging.error( "Other error: " +  str(room_id))
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
    response = urllib2.urlopen(url)
    page = response.read()
    return page

def get_search_page(url):
    # chrome gets the JavaScript-loaded content as well
    # see http://webscraping.com/blog/Scraping-JavaScript-webpages-with-webkit/
    #r = Render(url)
    #page = r.frame.toHtml()
    response = urllib2.urlopen(url)
    page = response.read()
    return page

def get_room_info(room_id, target_city):
    try:
        # initialization
        logging.info("Getting info for room " + str(room_id))
        room_url = ROOT_URL + str(room_id)
        page = get_page(room_url)
        if not get_room_info_from_page(page, room_id, "ny"):
            get_room_info_from_page(page, room_id, "sf")
        return True
    except KeyboardInterrupt:
        sys.exit()
    except:
        return False

def get_room_info_from_page(page, room_id, target_city):
    #try:
        #print page
            #except UnicodeEncodeError:
        #if sys.version_info >= (3,):
            #print(page.encode('utf8').decode(sys.stdout.encoding))
        #else:
            #print(page.encode('utf8'))
            #print page.encode('utf8', 'replace')
    try:
        empty = False
        host_id, room_type, country, city, \
                neighborhood, address, reviews, overall_satisfaction,\
                accommodates, bedrooms, bathrooms, price, deleted, minstay = \
                None, None, None, None, \
                None, None, None, None, \
                None, None, None, None, 0, 1
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
                deleted,
                minstay,
                )
        rooms_nearby = []
        tree = html.fromstring(page)
        host_id_element = tree.xpath(
            "//div[@id='user']"
            "//a[contains(@href,'/users/show')]"
            "/@href"
        )[0]
        host_id_offset = len('/users/show/')
        host_id = int(host_id_element[host_id_offset:])
        room_type = tree.xpath(
            "//table[@id='description_details']"
            "//td[text()[contains(.,'Room type:')]]"
            "/following-sibling::td/text()"
            )[0]
        country = tree.xpath( "//table[@id='description_details']"
            "//td[text()[contains(.,'Country:')]]"
            "/following-sibling::td/descendant::text()"
            )[0]
        city = tree.xpath( "//table[@id='description_details']"
            "//td[text()[contains(.,'City:')]]"
            "/following-sibling::td/descendant::text()"
            )[0]
        temp = tree.xpath( "//table[@id='description_details']"
            "//td[text()[contains(.,'Neighborhood:')]]"
            "/following-sibling::td/descendant::text()"
            )
        if len(temp) > 0: neighborhood = temp[0]
        address = tree.xpath(
            "//span[@id='display-address']"
            "/@data-location"
            )[0]
        reviews = tree.xpath(
            "//span[@itemprop='reviewCount']/text()"
            )[0]
        if target_city == "sf":
            overall_satisfaction = len(tree.xpath(
                "//div[@id='review-summary']"
                # "/div[@class='span3']"
                "/div[@class='col-3']"
                "//div[@class='foreground']"
                "/i[@class='icon icon-pink icon-star']"
                ))
            overall_satisfaction_half = len(tree.xpath(
                "//div[@id='review-summary']"
                #"/div[@class='span3']"
                "/div[@class='col-3']"
                "//div[@class='foreground']"
                "/i[@class='icon icon-pink icon-star-half']"
                ))
        else:
            overall_satisfaction = len(tree.xpath(
                "//div[@id='review-summary']"
                "/div[@class='span3']"
                # "/div[@class='col-3']"
                "//div[@class='foreground']"
                "/i[@class='icon icon-pink icon-star']"
                ))
            overall_satisfaction_half = len(tree.xpath(
                "//div[@id='review-summary']"
                "/div[@class='span3']"
                # "/div[@class='col-3']"
                "//div[@class='foreground']"
                "/i[@class='icon icon-pink icon-star-half']"
                ))
        overall_satisfaction += 0.5 * overall_satisfaction_half
        accommodates = tree.xpath( "//table[@id='description_details']"
            "//td[text()[contains(.,'Accommodates:')]]"
            "/following-sibling::td/descendant::text()"
            )[0]
        bedrooms = tree.xpath( "//table[@id='description_details']"
            "//td[text()[contains(.,'Bedrooms:')]]"
            "/following-sibling::td/descendant::text()"
            )
        if len(bedrooms) > 0:
            bedrooms = bedrooms[0]
        else:
            bedrooms = None
        bathrooms = tree.xpath( "//table[@id='description_details']"
            "//td[text()[contains(.,'Bathrooms:')]]"
            "/following-sibling::td/descendant::text()"
            )
        if len(bathrooms) > 0:
            bathrooms = bathrooms[0]
        else:
            bathrooms = None
        minstay = tree.xpath( "//table[@id='description_details']"
            "//td[text()[contains(.,'Minimum Stay:')]]"
            "/following-sibling::td/descendant::text()"
            )
        if len(minstay) > 0:
            minstay = minstay[0]
            non_decimal = re.compile(r'[^\d.]+')
            minstay = non_decimal.sub('', minstay)
        else:
            minstay = "1"
        if target_city == "sf":
            price = tree.xpath( "//div[@id='price_amount']/text()")[0][1:]
        else:
            price = tree.xpath( "//h2[@id='price_amount']/text()")[0][1:]
        # strip out non-numeric characters
        non_decimal = re.compile(r'[^\d.]+')
        price = non_decimal.sub('', price)
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
            deleted,
            minstay,
            )
        logging.debug("calling save_room_info")
        saved = save_room_info(room_info, True)
        return True
    except KeyboardInterrupt:
        sys.exit()
    except IndexError:
        #logging.error( "Web page has unexpected structure. Wrong city?")
        #traceback.print_exc(file=sys.stdout)
        return False
    except:
        traceback.print_exc(file=sys.stdout)
        return False

def loop_by_room(target_city):
    room_count = 0
    #if len(argv) > 1:
        #get_room_info(int(argv[1]), target_city)
        #room_count += 1
    while room_count < MAX_ROOM_COUNT:
        room_id = select_room()
        if room_id is None:
            break
        else:
            get_room_info(room_id, target_city)
            room_count += 1

def searcher(page_number):
    for room_type in ( "Private room", "Entire home/apt", "Shared room"):
        for neighborhood in neighborhoods_ny:
            for guests in xrange(1,5):
                logging.info("Page " + str(page_number) +
                        " for " + room_type + ", " + neighborhood +
                        ", " + str(guests) + " guests.")
                url_root_ny = "https://www.airbnb.ca/s/New-York--NY?"
                url = "guests=" + str(guests)
                url += urllib2.quote("&neighborhoods[]=" + neighborhood)
                url += urllib2.quote("&room_types[]=" + room_type)
                url += "&page=" + str(page_number)
                url = url_root_ny + url
                logging.debug(url)
                page = get_search_page(url)
                #try:
                #    print page
                #except UnicodeEncodeError:
                #    if sys.version_info >= (3,):
                #        print(s.encode('utf8').decode(sys.stdout.encoding))
                #    else:
                #        print(s.encode('utf8'))
                tree = html.fromstring(page)
                room_elements = tree.xpath(
                    "//ul[@id='results']"
                    #"//li[@class='search_result']"
                    #"//li/@id"
                    "//li"
                    #"//li[contains(@class,'search_result')]/@data-hosting-id"
                    #"/@data-hosting-id"
                )
                for room_element in room_elements:
                    room_id = room_element.get('data-hosting-id')
                    room_info = (room_id,
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
                        )
                    if room_id is not None:
                        save_room_info(room_info, False)

def main():
    parser = argparse.ArgumentParser(
            description='Manage a database of Airbnb listings.')
    parser.add_argument('-a', '--add',
            help='add a room_id to the database')
    parser.add_argument('-c', '--check',
            help='check if a room is in the database')
    parser.add_argument('-t', '--city',
            default="ny",
            help='ny or sf. airbnb uses different web page structure')
    parser.add_argument('-f', '--fill',
            action='store_true', default=False,
            help='fill in the details for collected room_ids')
    parser.add_argument('-s', '--search',
            action='store_true', default=False,
            help='search for rooms')
    args = parser.parse_args()
    try:
        create_table()
        target_city = args.city
        if args.search:
            for page in xrange(1,20):
                searcher(page)
        elif args.fill:
            loop_by_room(target_city)
        elif args.check:
            if check_room(int(args.check)):
                print "YES. Room", str(args.check), "is in the database."
            else:
                print "NO. Room", str(args.check), "is not in the database."
        elif args.add:
            get_room_info(int(args.add), target_city)
        else:
            print "Use -h for usage"

    except:
        traceback.print_exc(file=sys.stdout)

if __name__ == "__main__":
    main()
