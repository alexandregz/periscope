# -*- coding: utf-8 -*-

#
#   This file is part of periscope.
#
#    periscope is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    periscope is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with periscope; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

#
# Periscope plugin for http://tusubtitulo.com
# https://github.com/alexandregz/periscope 
# Alexandre Espinosa Menor <aemenor@gmail.com>
#

import zipfile, os, urllib2, urllib, logging, traceback, httplib, re
from BeautifulSoup import BeautifulSoup

import SubtitleDatabase

log = logging.getLogger(__name__)

LANGUAGES = {u"English (US)" : "en",
             u"English (UK)" : "en",
             u"English" : "en",
             u"French" : "fr",
             u"Brazilian" : "pt-br",
             u"Portuguese" : "pt",
             u"Español (Latinoamérica)" : "es",
             u"Español (España)" : "es",
             u"Español" : "es",
             u"Italian" : "it",
             u"Català" : "ca",
             u"Galego" : "gl"}

class Tusubtitulo(SubtitleDatabase.SubtitleDB):
    url = "http://www.tusubtitulo.com"
    site_name = "Tusubtitulo"

    def __init__(self, config, cache_folder_path):
        super(Tusubtitulo, self).__init__(langs=None,revertlangs=LANGUAGES)
        self.host = "http://www.tusubtitulo.com"
        self.release_pattern = re.compile("Versi&oacute;n (.+) ([0-9]+).([0-9])+ megabytes")
        

    def process(self, filepath, langs):
        ''' main method to call on the plugin, pass the filename and the wished 
        languages and it will query the subtitles source '''
        fname = unicode(self.getFileName(filepath).lower())
        guessedData = self.guessFileData(fname)
        if guessedData['type'] == 'tvshow':
            tvshow_data = self._get_tvshow_link(guessedData['name'])
            if tvshow_data['tvshow_path']:
                subs = self.query(tvshow_data['tvshow_name'], tvshow_data['tvshow_path'], guessedData['name'], guessedData['season'], guessedData['episode'], guessedData['teams'], langs)
                return subs
        else:
            return []


    def _get_tvshow_link(self, name):
        ''' search for tvshow page, returns tvshow_path and tvshow_name (we need real show name after) '''
        logging.debug("Using %s to search tvshow page" % name)
        url_tvshows = "http://www.tusubtitulo.com/series.php"

        page = urllib.urlopen(url_tvshows)
        content = page.read()
        soup = BeautifulSoup(content)

        name = name.replace(" ", "\.? ")

        links = soup.findAll("a")
        for a in soup.findAll("a"):
            if re.match(name, a.text, re.M|re.I):
                logging.debug("Found page %s" % a['href'])
                return { 'tvshow_path' : a['href'], 'tvshow_name' : a.text }
        return []

    
    def query(self, tvshow_name, tvshow_path, name, season, episode, teams, langs=None):
        ''' makes a query and returns info (link, lang) about found subtitles'''
        sublinks = []
        name = name.lower().replace(" ", "-")
        tvshow_name = tvshow_name.lower().replace(" ", "-")
        tvshow_path_id = tvshow_path.lower().replace("/show/", "")
        searchurl = "%s/serie/%s/%s/%s/%s" %(self.host, tvshow_name, season, episode, tvshow_path_id)

        content = self.downloadContent(searchurl, 10)
        if not content:
            return sublinks
        
        soup = BeautifulSoup(content)
        for subs in soup("div", {"id":"version"}):
            version = subs.find("p", {"class":"title-sub"})
            subteams = self.release_pattern.search("%s"%version.contents[1]).group(1).lower()            
            teams = set(teams)
            subteams = self.listTeams([subteams], [".", "_", " ", "/"])
            
            log.debug("Team from website: %s" %subteams)
            log.debug("Team from file: %s" %teams)

            nexts = subs.findAll("ul", {"class":"sslist"})
            for lang_html in nexts:
                langLI = lang_html.findNext("li",{"class":"li-idioma"} )
                lang = self.getLG(langLI.find("strong").contents[0].string.strip())
        
                statusLI = lang_html.findNext("li",{"class":"li-estado green"} )
                status = statusLI.contents[0].string.strip()

                link = statusLI.findNext("span", {"class":"descargar green"}).find("a")["href"]
                if status == "Completado" and subteams.issubset(teams) and (not langs or lang in langs) :
                    result = {}
                    result["release"] = "%s.S%.2dE%.2d.%s" %(name.replace("-", ".").title(), int(season), int(episode), '.'.join(subteams))
                    result["lang"] = lang
                    result["link"] = link
                    result["page"] = searchurl
                    sublinks.append(result)
                
        return sublinks
        
    def listTeams(self, subteams, separators):
        teams = []
        for sep in separators:
            subteams = self.splitTeam(subteams, sep)
        log.debug(subteams)
        return set(subteams)
    
    def splitTeam(self, subteams, sep):
        teams = []
        for t in subteams:
            teams += t.split(sep)
        return teams

    def createFile(self, subtitle):
        '''pass the URL of the sub and the file it matches, will unzip it
        and return the path to the created file'''
        suburl = subtitle["link"]
        videofilename = subtitle["filename"]
        srtbasefilename = videofilename.rsplit(".", 1)[0]
        srtfilename = srtbasefilename +".srt"
        self.downloadFile(suburl, srtfilename)
        return srtfilename

    def downloadFile(self, url, filename):
        ''' Downloads the given url to the given filename '''
        req = urllib2.Request(url, headers={'Referer' : url, 'User-Agent' : 'Mozilla/5.0 (X11; U; Linux x86_64; en-US; rv:1.9.1.3)'})
        
        f = urllib2.urlopen(req)
        dump = open(filename, "wb")
        dump.write(f.read())
        dump.close()
        f.close()
