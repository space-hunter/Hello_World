#	-*-	coding:	utf-8	-*-

from Plugins.Extensions.MediaPortal.resources.imports import *
from Plugins.Extensions.MediaPortal.resources.decrypt import *
import Queue
import threading
from Components.ScrollLabel import ScrollLabel
from enigma import loadJPG
from Tools.Directories import pathExists
from Components.ActionMap import *
from Components.Pixmap import Pixmap, MovingPixmap

from Components.AVSwitch import AVSwitch
from Components.Sources.List import List
from Components.ConfigList import ConfigList, ConfigListScreen

from Screens.Screen import Screen

# teilweise von movie2k geliehen
if fileExists('/usr/lib/enigma2/python/Plugins/Extensions/TMDb/plugin.pyo'):
	from Plugins.Extensions.TMDb.plugin import *
	TMDbPresent = True
elif fileExists('/usr/lib/enigma2/python/Plugins/Extensions/IMDb/plugin.pyo'):
	TMDbPresent = False
	IMDbPresent = True
	from Plugins.Extensions.IMDb.plugin import *
else:
	IMDbPresent = False
	TMDbPresent = False



T_INDEX = 0
T_FRAME_POS = 1
T_PAGE = 2
T_NAME = 3
T_FULL = 4


#thumbsFilmListe = [decodeHtml(name), url, imageurl]
	
	
class ShowThumbscreen(Screen):

	def __init__(self, session, thumbsFilmListe = [], filmpage = 0, filmpages = 0 ):
		self.session = session
		self.filmList = thumbsFilmListe
		self.filmpage = filmpage
		self.filmpages = filmpages
		print "eliinfo self.filmList:", self.filmList
		# groesse der Thubs definieren
		textsize = 20
		self.spaceX = 15
		self.picX = 180
		self.spaceY = 20
		self.picY = 260
		# Thumbs Geometrie, groesse und Anzahl berechnen
		size_w = getDesktop(0).size().width()
		size_h = getDesktop(0).size().height()
		self.thumbsX = size_w / (self.spaceX + self.picX) # thumbnails in X
		self.thumbsY = size_h / (self.spaceY + self.picY) # thumbnails in Y
		self.thumbsC = self.thumbsX * self.thumbsY # all thumbnails
		
		print "elitest size_w size_h :", size_w, size_h
		print "elitest thumbsX thumbsY thumbsC :", self.thumbsX, self.thumbsY, self.thumbsC
	
		#self.filmList = filmList
		#Skin XML der Thumbs erstellen 
		self.positionlist = []
		skincontent = ""
		posX = -1
		for x in range(self.thumbsC):
			posY = x / self.thumbsX
			posX += 1
			if posX >= self.thumbsX:
				posX = 0
			absX = self.spaceX + (posX*(self.spaceX + self.picX))
			absY = self.spaceY + (posY*(self.spaceY + self.picY))
			self.positionlist.append((absX, absY)) # Postition der Thumbs speichern um spaeter das Movingimage darzustellen
			skincontent += "<widget source=\"label" + str(x) + "\" render=\"Label\" position=\"" + str(absX+5) + "," + str(absY+self.picY-textsize) + "\" size=\"" + str(self.picX - 10) + ","  + str(textsize) + "\" font=\"mediaportal;14\" zPosition=\"2\" transparent=\"1\" noWrap=\"1\" valign=\"center\" halign=\"center\" foregroundColor=\"" + "#00ffffff" + "\" />"
			skincontent += "<widget name=\"thumb" + str(x) + "\" position=\"" + str(absX+5)+ "," + str(absY+5) + "\" size=\"" + str(self.picX -10) + "," + str(self.picY - (textsize*2)) + "\" zPosition=\"2\" transparent=\"1\" alphatest=\"blend\" />"

		# Load Boottons Skin XML
		self.plugin_path = mp_globals.pluginPath
		self.skin_path =  mp_globals.pluginPath + "/skins"
		path = "%s/%s/bottonsScreen.xml" % (self.skin_path, config.mediaportal.skin.value)
		if not fileExists(path):
			path = self.skin_path + "/original/bottonsScreen.xml"
		print path
		with open(path, "r") as f:
			skinbottons = f.read()
			f.close()
					
		#print "skinbottons", skinbottons 
		# Skin komlett aufbauen 
		self.skin_dump = ""
		self.skin_dump += "<screen position=\"0,0\" size=\"" + str(size_w) + "," + str(size_h) + "\" flags=\"wfNoBorder\" >"
		self.skin_dump += "<eLabel position=\"0,0\" zPosition=\"0\" size=\""+ str(size_w) + "," + str(size_h) + "\" backgroundColor=\"" + "#26181d20" + "\" />"
		#self.skin_dump += "<widget name=\"frame\" position=\"35,30\" size=\"190,200\" pixmap=\"/usr/lib/enigma2/python/Plugins/Extensions/mediaportal/skins/tec/images/pic_frame.png\" zPosition=\"1\" alphatest=\"blend\" />"
		self.skin_dump += "<widget name=\"frame\" position=\"" + str(absX+5)+ "," + str(absY+5) + "\" size=\"" +  str(self.picX) + "," + str(self.picY) + "\" pixmap=\"/usr/lib/enigma2/python/Plugins/Extensions/MediaPortal/images/pic_frame.png\" zPosition=\"1\" transparent=\"0\" alphatest=\"blend\" />"
		self.skin_dump += skincontent
		self.skin_dump += skinbottons
		self.skin_dump += "</screen>"
		self.skin = self.skin_dump
			
		Screen.__init__(self, session)
		
		#print "elitest SKIN:", self.skin

		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "EPGSelectActions", "WizardActions", "ColorActions", "NumberActions", "MenuActions", "MoviePlayerActions", "InfobarSeekActions"], {
			"cancel": self.keyCancel,
			"ok": self.keyOK,
			"left": self.key_left,
			"right": self.key_right,
			"up": self.key_up,
			"down": self.key_down,
			"info" :  self.keyTMDbInfo
			#"showEventInfo": self.StartExif
		}, -1)

		# Skin Variablen zuweisen	
		self['F1'] = Label("test")
		self['F2'] = Label("")
		self['F3'] = Label("")
		self['F4'] = Label("")
		self['Page'] = Label("Page:")
		self['page'] = Label("1/X")		

		self["frame"] = MovingPixmap()
		for x in range(self.thumbsC):
			self["label"+str(x)] = StaticText()
			self["thumb"+str(x)] = Pixmap()
#		self.Thumbnaillist = []
		self.filelist = []
		self.currPage = -1
		self.dirlistcount = 0
		#self.path = path

		index = 0
		framePos = 0
		Page = 0
		self.page = 0
		
		
		# filmlist um sparter den cursur zu setzen
		for x in self.filmList:
				self.filelist.append((index, framePos, Page, framePos, '/tmp/thumbs/' + str(framePos) + '.jpg'))
				index += 1
				framePos += 1
				if framePos > (self.thumbsC -1):
					framePos = 0
					Page += 1
		self.index = 0
		print "eliinfo self.filelist", self.filelist
		
		
		self.maxentry = len(self.filelist)-1
#		self.maxentry = self.thumbsX * self.thumbsY
		print "eliinfo self.maxentry", self.maxentry
#		self.index = lastindex - self.dirlistcount
	

		self.onLayoutFinish.append(self.dir)
		
		self.onLayoutFinish.append(self.layoutThumBFinished)
		self.paintFrame()
		
	def keyOK(self):
		self.streamLink = ""
		self.streamName = ""
		self.imageLink = ""		
		if self.maxentry < 0:
			return (None,None,None)
		self.old_index = self.index
		filmmummer = self.page * self.thumbsC + self.index
		print "eliinfo OK gedrueckt: self.filelist, self.index, self.page, filmmummer =", self.filelist, self.index, self.page, filmmummer
		
		self.streamLink = self.filmList[filmmummer][1]
		self.streamName = self.filmList[filmmummer][0]
		self.imageLink = self.filmList[filmmummer][2]
		print "eliinfo ausgewaehlter Filme", self.streamLink, self.streamName, self.imageLink
		self.close(self.streamLink, self.streamName, self.imageLink)	
		
	def keyCancel(self):
		self.close()

	def key_left(self):
		print "eliinfo self.maxentry, self.index, self.page", self.maxentry, self.index, self.page
		print "eliinfo T_FRAME_POS", T_FRAME_POS
		#print "eliinfo self.filelist", self.filelist
		print "eliinfo pos", self.filelist[self.index][T_FRAME_POS]
		self.index -= 1
		if self.index < 0:
			self.index = self.maxentry
		self.paintFrame()

	def key_right(self):
		self.index += 1
		print "eliinfo self.maxentry, self.index, self.page self.thumbsC", self.maxentry, self.index, self.page, self.thumbsC
		print "eliinfo T_FRAME_POS", T_FRAME_POS
		#print "eliinfo self.filelist", self.filelist
		print "eliinfo pos", self.filelist[self.index][T_FRAME_POS]
		
		if self.page*self.thumbsC+self.index > self.maxentry:
			self.index = 0
		if self.index > self.thumbsC:
			self.index = 0
		self.paintFrame()

	def key_up(self):
		print "eliinfo self.maxentry, self.index, self.page, roundpage ", self.maxentry, self.index, self.page, int(self.maxentry / self.thumbsC)
		print "eliinfo T_FRAME_POS", T_FRAME_POS
		#print "eliinfo self.filelist", self.filelist
		print "eliinfo pos", self.filelist[self.index][T_FRAME_POS]
		self.index -= self.thumbsX
		if self.index < 0:
			print "eliinfo zurueckblättern ?"
			if self.page > 0:
				print "eliinfo 1 Seite zurueckblaettern"
				self.page -= 1
				self.index = 0
				self.newThumbsPage()
			elif int(self.maxentry/self.thumbsC) > 0:
				print "eliinfo letze Seite anzeigen"
				self.page = int(self.maxentry / self.thumbsC)
				self.index = 0
				self.newThumbsPage()
			else:
				self.index += self.thumbsX
		self.paintFrame()

	def key_down(self):
		print "eliinfo self.maxentry, self.index, self.page", self.maxentry, self.index, self.page
		print "eliinfo T_FRAME_POS", T_FRAME_POS
		#print "eliinfo self.filelist", self.filelist
		print "eliinfo pos", self.filelist[self.index][T_FRAME_POS]
		self.index += self.thumbsX
		if self.page*self.thumbsC+self.index > self.maxentry:
#			print "eliinfo ende der liste-von anfang an",  self.page*self.thumbsC+self.index
#			self.index = 0
#			self.page = 0
#			self.newThumbsPage()
			self.close("next", "", "")
		elif self.index > self.thumbsC - 1:
			print "eliinfo Seitenwechsel self.page", self.page
			self.page += 1
			self.newThumbsPage()
		self.paintFrame()
		
	def keyTMDbInfo(self):
		if not self.keyLocked and TMDbPresent:
			title = self.filelist[self.page * self.thumbsC + self.index][0]
			self.session.open(TMDbMain, title)
		elif not self.keyLocked and IMDbPresent:
			title = self.filelist[self.page * self.thumbsC + self.index][0]
			self.session.open(IMDB, title)		
		

	def newThumbsPage(self):
		for x in range(self.thumbsC):
			print "eliinfo loesche bild", x
			self["label"+str(x)].setText("")
			self["thumb"+str(x)].hide()
		self.layoutThumBFinished()

	
	def paintFrame(self):
		print "eliinfo index=" + str(self.index)
		if self.maxentry < self.index or self.index < 0:
			return

		pos = self.positionlist[self.filelist[self.index][T_FRAME_POS]]
		self["frame"].moveTo( pos[0], pos[1], 1)
		self["frame"].startMoving()
		if self.page:
			self['page'].setText("%d / %d // %d / %d" % (self.page +1 , int(self.maxentry/self.thumbsC) +1, self.filmpage, self.filmpages))
		else:
			self['page'].setText("%d / %d // %d / %d" % (1 , int(self.maxentry/self.thumbsC) +1, self.filmpage, self.filmpages))
#		if self.currPage != self.filelist[self.index][T_PAGE]:
#			self.currPage = self.filelist[self.index][T_PAGE]
#			self.newPage()
	
	def dir(self):
		if not pathExists('/tmp/thumbs/'):
			os.system('mkdir /tmp/thumbs/')
			print '[Thumbsviewer]: /tmp/thumbs/ erstellt.'
		else:
			print '[Thumbsviewer]: /tmp/thumbs/ vorhanden.'

	def umlaute(self, text):
		text = text.replace('&nbsp;', ' ').replace('&#39;', "'").replace('&szlig;', '\xc3.').replace('&quot;', '"').replace('&ndash;', '-')
		text = text.replace('&copy;.*', ' ').replace('&amp;', '&').replace('&uuml;', '\xc3\xbc').replace('&auml;', '\xc3\xa4').replace('&ouml;', '\xc3\xb6')
		text = text.replace('&Uuml;', '\xc3.').replace('&Auml;', '\xc3.').replace('&Ouml;', '\xc3.')
		text = text.replace('\xe4', 'ae').replace('\xf6', 'oe').replace('\xfc', 'ue').replace('&#039;', "'")
		return text	
		
	def layoutThumBFinished(self):
		self.go = 'no'
		self.play = 'play'
		self.exit_now = 'exit'
		self.myTVmenulist = []
		self.own_playlist = []
		d = defer.Deferred()
		results = [None, None]
		thingsDone = 0	
		result = 0
		

		self.count = len(self.filmList)
		print '[Eliinfo]: self.count:', self.count
		self.loading = 0
		self.url_list = []	
		filmnummer = 0
		#thumbseite = self.page + 10

		# eliinfo - an der Filmliste eine Bildnummmer hinzufuegen ( Return zum Abspielen: filmUrl, filmName, imageLink)
		for each in range(self.page*self.thumbsC, self.page*self.thumbsC+self.thumbsC):
			try:
				title, filmlink, jpglink = self.filmList[each]
				jpg_store = '/tmp/thumbs/%s.jpg' % str(filmnummer)
				filmnummer += 1
				title = self.umlaute(title)
				self.url_list.append((title,
				 jpg_store,
				 filmlink,
				 jpglink))
			except IndexError:
				print "eliinfo ENDE der Liste"
		print "eliinsfo self.url_list", self.url_list
		line = 1
			
		self.showCoversLine()	
			
	def showCoversLine(self):
		self.index = 0
	
		#print '[Chartsplyer]: url_list', url_list	
#		self['info'].setText("Filme werden geladen")
		if len(self.url_list) != 0:
			ds = defer.DeferredSemaphore(tokens=1)
#			downloads = [ ds.run(self.download, item[3], item[1]).addCallback(self.get_xml, item[0], item[1], item[2], item[3]).addErrback(self.dataError) for item in url_list ]
			nr = 0
			downloads = []
			for x in self.url_list:	
				#for i in range(self.thumbsX):
					print "eliinfo Thumbs Screen Liste", self.url_list[nr]
					listhelper = ds.run(self.download, self.url_list[nr][3], self.url_list[nr][1]).addCallback(self.ShowCoverFile, self.url_list[nr][0], self.url_list[nr][1], self.url_list[nr][2], self.url_list[nr][3], nr).addErrback(self.dataError)
					downloads.append(listhelper)
					nr += 1
			finished = defer.DeferredList(downloads).addErrback(self.dataErrorfinished)
		print "Fertig mit Pic Download"
		
	
	
	def ShowCoverFile(self, data, title, picPath, filmlink, jpglink, nr):
		#print "eliinfo - Data fuer das Anzeigen eines Bildes", 	data, title, picPath, filmlink, jpglink, nr	
		self['label'+str(nr)].setText(title)
		if fileExists(picPath):
			self['thumb'+str(nr)].instance.setPixmap(None)
			self.scale = AVSwitch().getFramebufferScale()
			self.picload = ePicLoad()
			size = self['thumb'+str(nr)].instance.size()
			#print "eliinfo - Thumbs Size Nr + ", str(nr), size.width(), size.height(), self.scale[0], self.scale[1]
			self.picload.setPara((size.width(), size.height(), self.scale[0], self.scale[1], False, 1, "#FF000000"))
			if self.picload.startDecode(picPath, 0, 0, False) == 0:
				#print "eliinfo - startDecode"
				ptr = self.picload.getData()
				if ptr != None:
					#print "eliinfo - setPixmap and show"
					self['thumb'+str(nr)].instance.setPixmap(ptr.__deref__())
					self['thumb'+str(nr)].show()
					del self.picload
			
	def download(self, image, jpg_store):
		print '[eliinfo]: download image...image, jpg_store', image, jpg_store
		return downloadPage(image, jpg_store)

	def dataError(self, error):
		print "dataError:"
		
	def dataErrorfinished(self, error):
		print "dataErrorfinished:"				
