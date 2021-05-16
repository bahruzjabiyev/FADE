#!/usr/bin/python3
import gensim
import ast
import re
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from main import Main
from glob import glob
from base64 import b64decode


class Listener:
	main = Main()
	#mem_cache = {}

	#def __init__(self):
					

	def listen(self):
		clf = self.main.init_classifier()
		f2 = open('files/basewords_all_10K', 'r')
		lines = f2.readlines()
		f2.close()
		gen_docs = [ast.literal_eval(line[:-1]) for line in lines]
		dictionary = gensim.corpora.Dictionary(gen_docs)
		corpus = [dictionary.doc2bow(gen_doc) for gen_doc in gen_docs]
		tf_idf = gensim.models.TfidfModel(corpus)
		#dictionary = {}
		#corpus = []
		#tf_idf = []
		#clf = ""
		print("we are ready!")
		myHandler.needed_data = (dictionary, tf_idf, clf, self.main)

		'''Initializing the cache'''
		myHandler.mem_cache = {}
		for cache_file_name in glob('cached_articles/*txt'):
			myHandler.mem_cache[cache_file_name.replace("cached_articles/", "").replace(".txt", "")] = open(cache_file_name, "r").read()
	
		'''Starting the server'''	
		httpd = HTTPServer(('', 8080), myHandler)
		print(time.asctime(), "Server Starts - %s:%s" % ("localhost", 8080))
		httpd.serve_forever()


class myHandler(BaseHTTPRequestHandler):

	html_body = '''
		<html>
		<head>
		<link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.4.1/css/bootstrap.min.css" integrity="sha384-Vkoo8x4CGsO3+Hhxv8T/Q5PaXtkKtu6ug5TOeNV6gBiFeWPGFN9MuhOf23Q9Ifjh" crossorigin="anonymous">
		</head>
		<body>
		<div class="container" style="margin-top:5%">
		<ul class="list-group">
		  <li class="list-group-item">{}</li>
			{}
		</ul>
		</div>
		</body>
		</html>
	'''

	def do_GET(self):
		print(self.path)
		self.real_domains = [line.rstrip('\n') for line in open('files/real_domains.txt').readlines()]
		self.common_domains = [line.rstrip('\n') for line in open('files/common_domains.txt').readlines()]
		self.fake_domains = [line.rstrip('\n') for line in open('files/fake_domains.txt').readlines()]
		from_cache = True

		if "&from_cache=false" in self.path:
			from_cache = False

		if "/further_details?" in self.path:
			self.send_response(200)
			self.send_header("Content-type", "text/html")
			self.end_headers()
			encoded_urls = self.path.split("sources=")[1]
			main_article_domain = self.path.split('url=')[1].split('sources=')[0][:-1].split('/')[2]
			urls = str(b64decode(encoded_urls)).replace("'","")[3:-2].split()
			self.dict_sources = {'reputable':[], 'legitimate':[], 'fake':[], 'cited_fake':[]}
			for url in urls[2:]:#first two items are probabilities
				domain_name = ''
				if url.startswith('http'):#delete this if cond
					domain_name = url.split('/')[2]
				else:
					self.dict_sources['cited_fake'].append(url.replace("cited:",""))
					continue
				if domain_name == main_article_domain:
					continue
				if True in [domain_name == domain or domain_name.endswith('.'+domain) for domain in self.real_domains]:
					self.dict_sources['reputable'].append(url)
				if True in [domain_name == domain or domain_name.endswith('.'+domain) for domain in self.common_domains]:
					self.dict_sources['legitimate'].append(url)
				if True in [domain_name == domain or domain_name.endswith('.'+domain) for domain in self.fake_domains]:
					self.dict_sources['fake'].append(url)

			message, sources = self.make_tags()	
			self.wfile.write(bytes(self.html_body.format(message, sources), "utf-8"))
		else:
			start_time = time.time()
			self.send_response(200)
			self.send_header("Content-type", "text/html")
			url = self.path.split("url=")[1].split('from_cache=')[0][:-1]
			print(self.make_key(url))
			self.end_headers()
			#Cache operations
			keyed_url = self.make_key(url)
			if keyed_url in self.mem_cache and from_cache:
				response_value = self.mem_cache[keyed_url]
			else:
				response_value = str(self.needed_data[3].analyze(url, self.needed_data[0], self.needed_data[1], self.needed_data[2], start_time))
				self.mem_cache[keyed_url] = response_value
				cache_file = open('cached_articles/{}.txt'.format(keyed_url), 'w')
				cache_file.write(response_value)
	
			print(response_value)
			self.wfile.write(bytes(response_value, 'utf-8'))

	def make_key(self, url):
		return re.sub(r"[^a-z0-9]", "", url.lower())

	def make_tags(self):
		if len(self.dict_sources['legitimate']) + len(self.dict_sources['reputable']) == 0:
			message = "No major source found to publish this story."
		else:
			message = "Major sources found to publish this story, are listed below."
		return message, "".join(['<li class="list-group-item list-group-item-primary" title="a reputable source">{} published this <a href="{}">story</a>.</li>'.format(item.split('/')[2], item) for item in self.dict_sources['reputable']]) + "".join(['<li class="list-group-item list-group-item-success" title="a legitimate source">{} published this <a href="{}">story</a>.</li>'.format(item.split('/')[2], item) for item in self.dict_sources['legitimate']]) + "".join(['<li class="list-group-item list-group-item-danger" title="an unreliable source">{} published this <a href="{}">story</a> and this source is not reliable.</li>'.format(item.split('/')[2], item) for item in self.dict_sources['fake']]) + "".join(['<li class="list-group-item list-group-item-warning" title="cited unreliable source">{} is being cited and this source is not reliable.</li>'.format(item) for item in self.dict_sources['cited_fake']])

#main("https://www.theguardian.com/us-news/2017/nov/27/koch-brothers-time-magazine-media-power")
listener = Listener()
listener.listen()

'''
<html>
<head>
<link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.4.1/css/bootstrap.min.css" integrity="sha384-Vkoo8x4CGsO3+Hhxv8T/Q5PaXtkKtu6ug5TOeNV6gBiFeWPGFN9MuhOf23Q9Ifjh" crossorigin="anonymous">
</head>
<body>
<div class="container" style="margin-top:5%">
<ul class="list-group">
  <li class="list-group-item">Dapibus ac facilisis in</li>


  <li class="list-group-item list-group-item-primary">This is a primary list group item</li>
  <li class="list-group-item list-group-item-secondary">This is a secondary list group item</li>
  <li class="list-group-item list-group-item-success">This is a success list group item</li>
  <li class="list-group-item list-group-item-danger">This is a danger list group item</li>
  <li class="list-group-item list-group-item-warning">This is a warning list group item</li>
  <li class="list-group-item list-group-item-info">This is a info list group item</li>
  <li class="list-group-item list-group-item-light">This is a light list group item</li>
  <li class="list-group-item list-group-item-dark">This is a dark list group item</li>
</ul>
</div>
</body>
</html>
'''
