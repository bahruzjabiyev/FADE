#!/usr/bin/python3
import gensim
import sys
import linecache
import newspaper
from bs4 import BeautifulSoup
from urllib.request import urlopen
from urllib.parse import quote
import ast
import re
import time
import os
import multiprocessing
import nltk
from sklearn.svm import SVC

class Main:

	def __init__(self):
		self.real_domains = [line.rstrip('\n') for line in open('files/real_domains.txt').readlines()] 
		self.common_domains = [line.rstrip('\n') for line in open('files/common_domains.txt').readlines()] 
		self.fake_domains = [line.rstrip('\n') for line in open('files/fake_domains.txt').readlines()] 

	def PrintException(self):
		try:
			exc_type, exc_obj, tb = sys.exc_info()
			f = tb.tb_frame
			lineno = tb.tb_lineno
			filename = f.f_code.co_filename
			linecache.checkcache(filename)
			line = linecache.getline(filename, lineno, f.f_globals)
			print('EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj))
			
		except Exception as e:
			pass
	
	
	def analyze_search_result(self, article_date, res, lock):
		try:
			start_time = time.time()
			article = newspaper.Article(res)
			article.download()
			article.parse()
			res_date = article.publish_date
			if article_date != "None" and res_date is not None:
				if res_date.timestamp() - float(article_date) > 172800 or float(article_date) - res_date.timestamp() > 172800:
					return
			words = self.LemNormalize((article.title + " " + article.text).replace("\\n"," ").replace("\n"," "))
			analysis_result = ((words, res))
			with lock:
				f = open('result','a')
				f.write(str(analysis_result) + "\n")
				f.close()
			#print("It took {:.2f} seconds to analyze {}".format(time.time()-start_time, res))
		except newspaper.article.ArticleException as e:
			self.PrintException()
		except Exception as e:
			self.PrintException()

	def LemTokens(self, tokens):
		lemmer = nltk.stem.WordNetLemmatizer()
		return [lemmer.lemmatize(token) for token in tokens]
	
	def LemNormalize(self, text):
		remove_punct_dict = dict((ord(punct), None) for punct in '''!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~–‚⁄´“”‘’»«˝˜…•—''')
		return self.LemTokens(nltk.word_tokenize(text.lower().translate(remove_punct_dict)))
	
	
	def duck_keywords(self, keywords):
		try:
			search_url = 'https://duckduckgo.com/?q=' + str(keywords)[1:-1].replace("'","%27").replace(",","%2C").replace(" ","+") + '&t=hf&ia=web'
			print(search_url)
			page = urlopen(search_url)
			soup = BeautifulSoup(page, 'html.parser')
			url = re.findall(r"/d.js[^']*",str(soup))[0]
			page2 = urlopen("https://duckduckgo.com" + url)
			soup2 = BeautifulSoup(page2, 'html.parser')
			duck_results = list(set([result for result in re.findall(r'en":\[[^\]]*',str(soup2))[0][6:-1].split('","') if result.find('.pdf') == -1]))
			return duck_results
		except:
			return []
	
	
	def duckduckgo(self, article_date, title, keywords):
		try:
			search_url = 'https://duckduckgo.com/?q=' + quote(title) + '&t=hf&ia=web'
			page = urlopen(search_url)
			soup = BeautifulSoup(page, 'html.parser')
			url = re.findall(r"/d.js[^']*",str(soup))[0]
			page2 = urlopen("https://duckduckgo.com" + url)
			soup2 = BeautifulSoup(page2, 'html.parser')
			processes = {}
			times = {}
			duck_results = list(set([result for result in re.findall(r'en":\[[^\]]*',str(soup2))[0][6:-1].split('","') if result.find('.pdf') == -1]))
			duck_keyword_results = self.duck_keywords(keywords)
			duck_results = list(set(duck_results + duck_keyword_results))
	
			lock = multiprocessing.Lock()
			for i in range(len(duck_results)):
				processes[i] = multiprocessing.Process(target=self.analyze_search_result, args=(article_date, duck_results[i],lock))
				processes[i].start()
				times[i] = time.time()
				print("started process {}".format(i))
	
			for i in range(len(processes)):
				process = processes[i]
				process.join(10)
				if process.exitcode is None:
					process.terminate()
					f = open('trash','a')
					f.write(str(i) + "." + duck_results[i] + "\n")
					f.close()
	
			f = open('result','r')
			lines = f.readlines()
			f.close()
			os.remove('result')
			return (([line[2:-3].split("], ")[0][1:-1].split("', '") for line in lines], [line[2:-3].split("], ")[1][1:]  for line in lines]))
	
		except Exception as e:
			self.PrintException()
			return None


	
	def download_article(self, url):
		try:
			trantab = str.maketrans('''!·£™"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~–‚⁄´“”‘’»«˝˜…•—''', 50 * '.')
			article = newspaper.Article(url)
			article.download()
			article.parse()
			article.nlp()
			keywords = article.keywords
			article_date = article.publish_date
			filename = url.translate(trantab)[:100] + ".txt"
			f = open(filename, "w")
			f.write(article.title + "\n")
			f.write(article.text + "\n")
			f.close()
			if article_date is not None:
				date = str(article_date.timestamp())
			else:
				date = "None"
			return (filename, keywords, date) 
		except Exception as e:
			self.PrintException()
			return None
	
	def init_classifier(self):
		train_x = []
		train_y = []
		f = open('files/data_newest_csv','r')
		for row in f:
			splitted = row.strip().split(',')
			train_x.append(splitted[:-1])
			train_y.append(int(splitted[-1]))
		f.close()
		clf = SVC(probability=True)
		clf.fit(train_x, train_y)
		return clf
	
	def sanitize(self, url):
		if "web.archive.org/" in url:
			return url[url[5:].find('http')+5:]
		elif "webcache.googleusercontent.com" in url:
			return "http://" + ('/'.join(url.split(':')[-1].split('/')[:-1]))
		else:
			return url
	
	def flatten_double_list(self, double_list):
		return [x for b in double_list for x in b]
	
	
	def check_external_urls(self, url):
		try:
	
			article = newspaper.Article(url)
			article.download()
			article.parse()
			text = article.text
			html = article.html
	
			url = self.sanitize(url)
	
			if text.find(article.title) == -1:
				start_from = 0
			else:
				start_from = len(article.title)
	
			found_flag1 = False
			for i in range(10):
				fst = " ".join(text[start_from:].split()[i*5:(i+1)*5])
				pos1 = html.find(fst)
				if pos1 != -1:
					found_flag1 = True
					break
	
			if not found_flag1:
				return 0
	
			found_flag2 = False
			for i in range(10):
				lst = " ".join(text[start_from:].split()[(i+1)*(-5)-1:i*(-5)-1])
				pos2 = html.find(lst)
				if pos2 != -1:
					found_flag2 = True
					break
	
			if not found_flag2:
				return 0
	
			urls = re.findall(r'''http.?://[^'" ]*''',html[pos1:pos2])
			urls = [self.sanitize(url.lower()) for url in urls]
			main_domain = url.split("/")[2].lstrip("www.")
			if ":" in main_domain:
				index = main_domain.find(":")
				main_domain = main_domain[:index]
	
			fake_domains_for_external = ["."+dom for dom in self.fake_domains] + ["/"+dom for dom in self.fake_domains]
			list1 = [[fake_domain[1:] for fake_domain in fake_domains_for_external if fake_domain in urlitem] for urlitem in urls if main_domain not in urlitem]
			return (len(set(self.flatten_double_list(list1))), list(set(self.flatten_double_list(list1))))
	
		except Exception as e:
			print(e)
			return 0
	
	def analyze(self, url, dictionary, tf_idf, clf, start_time):
		try:
			filename, keywords, date = self.download_article(url)
			f = open(filename, "r")
			lines = f.readlines()
			f.close()
			words_to_lemmatize = lines[0].rstrip('\n') + " " + " ".join(
				[line.replace("\\n", " ").replace("\n", " ") for line in lines[1:-1]])
			words = self.LemNormalize(words_to_lemmatize)
			title = lines[0].rstrip('\n')
			index = gensim.similarities.MatrixSimilarity([tf_idf[dictionary.doc2bow(words)]], num_features=len(dictionary))
			sim_list = []
			docs_and_results = self.duckduckgo(date, title, keywords)
			for i, val in enumerate(docs_and_results[0]):
				sim_amount = index[tf_idf[dictionary.doc2bow(val)]][0]
				sim_list.append((docs_and_results[1][i], sim_amount))
			
			for item in sorted(sim_list, key=lambda x:x[1], reverse=True):
				print(item)
	
			all_similarity_domains = {}
			for k in range(4,10):
				all_similarity_domains[k] = [item[0].split("/")[2] for item in sim_list if float(item[1]) > float(k)/10 and float(item[1]) <= float(k+1)/10 and url.rstrip('/').lstrip('http://').lstrip('https://').lower() not in item[0].lower() and item[0].rstrip('/').lstrip('http://').lstrip('https://').lower() not in url.lower()]
	
			all_similarity_features_tuple = ()
			for domains in all_similarity_domains.values():
				all_similarity_features_tuple += (len(set(self.flatten_double_list([[real_domain for real_domain in self.real_domains if domain.endswith("."+real_domain) or domain == real_domain] for domain in domains]))) , len(set(self.flatten_double_list([[common_domain for common_domain in self.common_domains if domain.endswith("."+common_domain) or domain == common_domain] for domain in domains]))), len(set(self.flatten_double_list([[fake_domain for fake_domain in self.fake_domains if domain.endswith("."+fake_domain) or domain == fake_domain] for domain in domains]))))

			num_cited_fake_sources, cited_urls = self.check_external_urls(url)
			all_feature_values = (num_cited_fake_sources,) + all_similarity_features_tuple
			print(all_feature_values)
			proba_result = clf.predict_proba([list(all_feature_values)])
			time_records_file = open('base_times','a')
			time_records_file.write("{:.2f}\n".format(time.time() - start_time))
			time_records_file.close()
			return list(proba_result[0]) + [item[0] for item in sim_list if item[1]>0.4] + ["cited:{}".format(url) for url in cited_urls] 
	
		except Exception as e:
			self.PrintException()
			print(e)
			return None
