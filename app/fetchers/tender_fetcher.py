"""
Advanced tender fetching system with multiple sources and robust error handling
"""
import requests
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import random
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import logging
from app.models import Tender, FetchLog
from app import db
import json
from fake_useragent import UserAgent
import re
from playwright.sync_api import sync_playwright
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from app.utils.ai_analyzer import AIAnalyzer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TenderFetcher:
    """
    Main class for fetching tenders from multiple sources
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.ua = UserAgent()
        self.ai_analyzer = AIAnalyzer()
        # Set up headers to avoid basic blocking
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # List of all sources to fetch from
        self.sources = [
            # Primary eProcurement Portals
            {'name': 'GEM', 'url': 'https://gem.gov.in/', 'method': 'gem'},
            {'name': 'eProcure', 'url': 'https://eprocure.gov.in/eprocure/app', 'method': 'eprocure'},
            {'name': 'CPWD', 'url': 'https://etender.cpwd.gov.in/', 'method': 'cpwd'},
            
            # Bihar State Portals
            {'name': 'Bihar eProc2', 'url': 'https://eproc2.bihar.gov.in/', 'method': 'bihar_eproc2'},
            {'name': 'Bihar UIDCO', 'url': 'https://www.buidco.in/ActiveTenders.aspx', 'method': 'buidco'},
            {'name': 'Bihar Mines', 'url': 'http://bmsicl.gov.in/node/53', 'method': 'bmsicl'},
            {'name': 'Bihar Health Services', 'url': 'https://shs.bihar.gov.in/Tender', 'method': 'bihar_health'},
            {'name': 'Bihar SEIDC', 'url': 'https://bseidc.in/active_tender.php', 'method': 'bseidc'},
            {'name': 'Bihar Rural Water', 'url': 'https://rwdbihar.gov.in/', 'method': 'rwd_bihar'},
            {'name': 'Bihar Roads', 'url': 'https://roads.bihar.gov.in/', 'method': 'roads_bihar'},
            {'name': 'Bihar Power', 'url': 'https://sbpdcl.co.in/', 'method': 'sbpdcl'},
            {'name': 'Bihar NE Power', 'url': 'https://nbpdcl.co.in/', 'method': 'nbpdcl'},
            {'name': 'Bihar HPCL', 'url': 'https://bsphcl.bih.nic.in/', 'method': 'bsphcl'},
            {'name': 'Bihar Tourism', 'url': 'https://bstdc.bihar.gov.in/tenders.htm', 'method': 'bstdc'},
            {'name': 'Bihar Electronics', 'url': 'https://beltron.bihar.gov.in/', 'method': 'beltron'},
            {'name': 'Bihar Industrial Area', 'url': 'https://biada.co.in/', 'method': 'biada'},
            {'name': 'Bihar PHED', 'url': 'https://phed.bihar.gov.in/', 'method': 'phed_bihar'},
            {'name': 'Bihar Water Resources', 'url': 'https://waterresources.bihar.gov.in/', 'method': 'water_bihar'},
            {'name': 'BRBN', 'url': 'https://brbn.bihar.gov.in/', 'method': 'brbn'},
            {'name': 'Bihar Building', 'url': 'https://bpbcc.in/', 'method': 'bpbcc'},
            {'name': 'BRLPS', 'url': 'https://brlps.in/', 'method': 'brlps'},
            {'name': 'Sudha Dairy', 'url': 'https://sudha.coop/', 'method': 'sudha'},
            {'name': 'Patna Smart City', 'url': 'https://patnasmartcity.in/', 'method': 'patna_smart'},
            {'name': 'Muzaffarpur Smart City', 'url': 'https://muzaffarpursmartcity.in/', 'method': 'muz_smart'},
            {'name': 'Bihar Sharif Smart City', 'url': 'https://biharsharifsmc.com/', 'method': 'bih_sharif_smc'},
            {'name': 'PMCP Patna', 'url': 'https://pmcpatna.in/', 'method': 'pmcp_patna'},
            {'name': 'Bihar State Bank', 'url': 'https://bsbccl.bihar.gov.in/New_V/NewTenderDetails.aspx?TenderD=NewTenderDetails.aspx', 'method': 'bsbccl'},
            
            # Bihar Education
            {'name': 'BEPCSSA', 'url': 'https://www.bepcssa.in/en/tenders.php', 'method': 'bepcssa'},
            {'name': 'Bihar Board', 'url': 'https://biharboardonline.bihar.gov.in/', 'method': 'bihar_board'},
            
            # Bihar District Portals (NIC)
            {'name': 'Patna NIC', 'url': 'https://patna.nic.in/notice_category/tenders/', 'method': 'patna_nic'},
            {'name': 'Muzaffarpur NIC', 'url': 'https://muzaffarpur.nic.in/notice_category/district-tender/', 'method': 'muz_nic'},
            {'name': 'Gaya NIC', 'url': 'https://gaya.nic.in/notice_category/tenders/', 'method': 'gaya_nic'},
            {'name': 'Bhagalpur NIC', 'url': 'https://bhagalpur.nic.in/notice_category/tenders/', 'method': 'bhagal_nic'},
            {'name': 'Darbhanga NIC', 'url': 'https://darbhanga.nic.in/notice_category/tenders/', 'method': 'darbh_nic'},
            {'name': 'Vaishali NIC', 'url': 'https://vaishali.nic.in/notice_category/tenders/', 'method': 'vaish_nic'},
            {'name': 'Saran NIC', 'url': 'https://saran.nic.in/notice_category/tenders/', 'method': 'saran_nic'},
            {'name': 'Sitamarhi NIC', 'url': 'https://sitamarhi.nic.in/notice_category/tenders/', 'method': 'sitamar_nic'},
            {'name': 'Siwan NIC', 'url': 'https://siwan.nic.in/notice_category/tenders/', 'method': 'siwan_nic'},
            {'name': 'Gopalganj NIC', 'url': 'https://gopalganj.nic.in/notice_category/tenders/', 'method': 'gopal_nic'},
            {'name': 'East Champaran NIC', 'url': 'https://eastchamparan.nic.in/notice_category/tenders/', 'method': 'ec_nic'},
            {'name': 'West Champaran NIC', 'url': 'https://westchamparan.nic.in/notice_category/tenders/', 'method': 'wc_nic'},
            {'name': 'Samastipur NIC', 'url': 'https://samastipur.nic.in/notice_category/tenders/', 'method': 'samas_nic'},
            {'name': 'Begusarai NIC', 'url': 'https://begusarai.nic.in/notice_category/tenders/', 'method': 'beg_nic'},
            {'name': 'Munger NIC', 'url': 'https://munger.nic.in/notice_category/tenders/', 'method': 'munger_nic'},
            {'name': 'Jamui NIC', 'url': 'https://jamui.nic.in/notice_category/tenders/', 'method': 'jamui_nic'},
            {'name': 'Lakhisarai NIC', 'url': 'https://lakhisarai.nic.in/notice_category/tenders/', 'method': 'lakhi_nic'},
            {'name': 'Sheikhpura NIC', 'url': 'https://sheikhpura.nic.in/notice_category/tenders/', 'method': 'sheikh_nic'},
            {'name': 'Nalanda NIC', 'url': 'https://nalanda.nic.in/notice_category/tenders/', 'method': 'nalanda_nic'},
            {'name': 'Nawada NIC', 'url': 'https://nawada.nic.in/notice_category/tenders/', 'method': 'nawada_nic'},
            {'name': 'Aurangabad NIC', 'url': 'https://aurangabad.bih.nic.in/notice_category/tenders/', 'method': 'aurang_nic'},
            {'name': 'Jehanabad NIC', 'url': 'https://jehanabad.nic.in/notice_category/tenders/', 'method': 'jehan_nic'},
            {'name': 'Arwal NIC', 'url': 'https://arwal.nic.in/notice_category/tenders/', 'method': 'arwal_nic'},
            {'name': 'Rohtas NIC', 'url': 'https://rohtas.nic.in/notice_category/tenders/', 'method': 'rohtas_nic'},
            {'name': 'Buxar NIC', 'url': 'https://buxar.nic.in/notice_category/tenders/', 'method': 'buxar_nic'},
            {'name': 'Bhojpur NIC', 'url': 'https://bhojpur.nic.in/notice_category/tenders/', 'method': 'bhojpur_nic'},
            {'name': 'Kaimur NIC', 'url': 'https://kaimur.nic.in/notice_category/tenders/', 'method': 'kaimur_nic'},
            {'name': 'Supaul NIC', 'url': 'https://supaul.nic.in/notice_category/tenders/', 'method': 'supaul_nic'},
            {'name': 'Purnia NIC', 'url': 'https://purnia.nic.in/notice_category/tenders/', 'method': 'purnia_nic'},
            {'name': 'Katihar NIC', 'url': 'https://katihar.nic.in/notice_category/tenders/', 'method': 'katihar_nic'},
            {'name': 'Araria NIC', 'url': 'https://araria.nic.in/notice_category/tenders/', 'method': 'araria_nic'},
            {'name': 'Kishanganj NIC', 'url': 'https://kishanganj.nic.in/notice_category/tenders/', 'method': 'kish_nic'},
            {'name': 'Madhubani NIC', 'url': 'https://madhubani.nic.in/notice_category/tenders/', 'method': 'madhubani_nic'},
            {'name': 'Khagaria NIC', 'url': 'https://khagaria.nic.in/notice_category/tenders/', 'method': 'khagaria_nic'},
            {'name': 'Sheohar NIC', 'url': 'https://sheohar.nic.in/notice_category/tenders/', 'method': 'sheohar_nic'},
            
            # Jharkhand State Portals
            {'name': 'Jharkhand Tenders', 'url': 'https://jharkhandtenders.gov.in/', 'method': 'jharkhand_tenders'},
            {'name': 'JSBCCL', 'url': 'https://jsbccl.jharkhand.gov.in/tenders', 'method': 'jsbccl'},
            {'name': 'JBVNL', 'url': 'https://jbvnl.co.in/', 'method': 'jbvnl'},
            {'name': 'JUVNL', 'url': 'https://juvnl.co.in/', 'method': 'juvnl'},
            {'name': 'JUIDCO', 'url': 'https://juidco.jharkhand.gov.in/', 'method': 'juidco'},
            {'name': 'JSMDC', 'url': 'https://www.jsmdc.in/', 'method': 'jsmdc'},
            {'name': 'JREDA', 'url': 'https://jreda.jharkhand.gov.in/', 'method': 'jreda'},
            {'name': 'JEPC', 'url': 'https://jepc.co.in/', 'method': 'jepc'},
            {'name': 'Ranchi Municipal', 'url': 'https://ranchimunicipal.com/', 'method': 'ranchi_muni'},
            
            # Jharkhand District Portals (NIC)
            {'name': 'Ranchi NIC', 'url': 'https://ranchi.nic.in/notice_category/tenders/', 'method': 'ranchi_nic'},
            {'name': 'Dhanbad NIC', 'url': 'https://dhanbad.nic.in/notice_category/tenders/', 'method': 'dhanbad_nic'},
            {'name': 'Hazaribag NIC', 'url': 'https://hazaribag.nic.in/notice_category/tenders/', 'method': 'hazari_nic'},
            {'name': 'Bokaro NIC', 'url': 'https://bokaro.nic.in/notice_category/tenders/', 'method': 'bokaro_nic'},
            {'name': 'Jamshedpur NIC', 'url': 'https://jamshedpur.nic.in/notice_category/tenders/', 'method': 'jamshed_nic'},
            {'name': 'Chaibasa NIC', 'url': 'https://chaibasa.nic.in/notice_category/tenders/', 'method': 'chaibasa_nic'},
            {'name': 'Palamu NIC', 'url': 'https://palamu.nic.in/notice_category/tenders/', 'method': 'palamu_nic'},
            {'name': 'Seraikela NIC', 'url': 'https://seraikela.nic.in/notice_category/tenders/', 'method': 'seraikela_nic'},
            {'name': 'Dumka NIC', 'url': 'https://dumka.nic.in/notice_category/tenders/', 'method': 'dumka_nic'},
            {'name': 'Giridih NIC', 'url': 'https://giridih.nic.in/notice_category/tenders/', 'method': 'giridih_nic'},
            {'name': 'Latehar NIC', 'url': 'https://latehar.nic.in/notice_category/tenders/', 'method': 'latehar_nic'},
            {'name': 'Pakur NIC', 'url': 'https://pakur.nic.in/notice_category/tenders/', 'method': 'pakur_nic'},
            {'name': 'Sahibganj NIC', 'url': 'https://sahibganj.nic.in/notice_category/tenders/', 'method': 'sahib_nic'},
            {'name': 'Simdega NIC', 'url': 'https://simdega.nic.in/notice_category/tenders/', 'method': 'simdega_nic'},
            {'name': 'Khunti NIC', 'url': 'https://khunti.nic.in/notice_category/tenders/', 'method': 'khunti_nic'},
            {'name': 'Ramgarh NIC', 'url': 'https://ramgarh.nic.in/notice_category/tenders/', 'method': 'ramgarh_nic'},
            {'name': 'Lohardaga NIC', 'url': 'https://lohardaga.nic.in/notice_category/tenders/', 'method': 'lohard_nic'},
            {'name': 'Koderma NIC', 'url': 'https://koderma.nic.in/notice_category/tenders/', 'method': 'koderma_nic'},
            {'name': 'Deoghar NIC', 'url': 'https://deoghar.nic.in/notice_category/tenders/', 'method': 'deoghar_nic'},
            {'name': 'Godda NIC', 'url': 'https://godda.nic.in/notice_category/tenders/', 'method': 'godda_nic'},
            {'name': 'Gumla NIC', 'url': 'https://gumla.nic.in/notice_category/tenders/', 'method': 'gumla_nic'},
            {'name': 'Chatra NIC', 'url': 'https://chatra.nic.in/notice_category/tenders/', 'method': 'chatra_nic'},
            {'name': 'Garhwa NIC', 'url': 'https://garhwa.nic.in/notice_category/tenders/', 'method': 'garhwa_nic'},
            {'name': 'Jamtara NIC', 'url': 'https://jamtara.nic.in/notice_category/tenders/', 'method': 'jamtara_nic'},
            
            # Indian Railways
            {'name': 'IREPS', 'url': 'https://www.ireps.gov.in/', 'method': 'ireps'},
            {'name': 'ECR Railway', 'url': 'https://ecr.indianrailways.gov.in/', 'method': 'ecr_rail'},
            {'name': 'SER Railway', 'url': 'https://ser.indianrailways.gov.in/', 'method': 'ser_rail'},
            {'name': 'ER Railway', 'url': 'https://er.indianrailways.gov.in/', 'method': 'er_rail'},
            {'name': 'RVNL', 'url': 'https://rvnl.org/tenders', 'method': 'rvnl'},
            {'name': 'RITES', 'url': 'https://www.rites.com/web/index.php/tender', 'method': 'rites'},
            {'name': 'IRCON', 'url': 'https://ircon.org/index.php/tender', 'method': 'ircon'},
            {'name': 'Rail Vikas', 'url': 'https://www.railvikas.gov.in/', 'method': 'rail_vikas'},
            
            # Hospitals - Bihar
            {'name': 'AIIMS Patna', 'url': 'https://aiimspatna.edu.in/tender/', 'method': 'aiims_patna'},
            {'name': 'IGIMS', 'url': 'https://igims.org/', 'method': 'igims'},
            {'name': 'Mahavir Cancer', 'url': 'https://www.mahavircancersansthan.org/', 'method': 'mahavir_cancer'},
            {'name': 'RMRIMS', 'url': 'https://rmrims.org.in/', 'method': 'rmrims'},
            {'name': 'ESIC', 'url': 'https://esic.in/tenders/', 'method': 'esic'},
            
            # Hospitals - Jharkhand
            {'name': 'RIMS', 'url': 'https://www.rims.ac.in/', 'method': 'rims_jh'},
            {'name': 'AIIMS Deoghar', 'url': 'https://aiimsdeoghar.edu.in/', 'method': 'aiims_deo'},
            
            # Universities - Bihar
            {'name': 'IIT Patna', 'url': 'https://www.iitp.ac.in/index.php/en-us/tenders', 'method': 'iit_patna'},
            {'name': 'NIT Patna', 'url': 'https://www.nitp.ac.in/tenders', 'method': 'nit_patna'},
            {'name': 'IIM Bodhgaya', 'url': 'https://iimbg.ac.in/', 'method': 'iim_bg'},
            {'name': 'NIPER Hajipur', 'url': 'https://www.niperhajipur.ac.in/', 'method': 'niper_haj'},
            {'name': 'IIIT Bhagalpur', 'url': 'https://iiitbh.ac.in/', 'method': 'iiit_bhagal'},
            {'name': 'CUSAT Bihar', 'url': 'https://cusb.ac.in/', 'method': 'cusb'},
            {'name': 'Nalanda University', 'url': 'https://nalandauniv.edu.in/', 'method': 'nalanda_univ'},
            {'name': 'MGCU', 'url': 'https://mgcub.ac.in/', 'method': 'mgcub'},
            {'name': 'RPCAU', 'url': 'https://rpcau.ac.in/', 'method': 'rpcau'},
            {'name': 'BAU Sabour', 'url': 'https://bausabour.ac.in/', 'method': 'bau_sabour'},
            {'name': 'Patna University', 'url': 'https://patnauniversity.ac.in/', 'method': 'patna_univ'},
            {'name': 'Bhupendra Narayan Mandal University', 'url': 'https://basu.ac.in/', 'method': 'basu'},
            
            # Universities - Jharkhand
            {'name': 'NIT Jamshedpur', 'url': 'https://nitjsr.ac.in/', 'method': 'nit_jsr'},
            {'name': 'IIT ISM Dhanbad', 'url': 'https://www.iitism.ac.in/index.php/tenders', 'method': 'iit_ism'},
            {'name': 'BIT Mesra', 'url': 'https://www.bitmesra.ac.in/', 'method': 'bit_mesra'},
            {'name': 'Ranchi University', 'url': 'https://www.ranchiuniversity.ac.in/', 'method': 'ranchi_univ'},
            {'name': 'VBU Hazaribagh', 'url': 'https://www.vbu.ac.in/', 'method': 'vbu'},
            {'name': 'Kolhan University', 'url': 'https://www.kolhanuniversity.ac.in/', 'method': 'kolhan_univ'},
            {'name': 'Cochin University', 'url': 'https://cuj.ac.in/tenders.php', 'method': 'cuj'},
            {'name': 'BITS Sindri', 'url': 'https://www.bitsindri.ac.in/', 'method': 'bits_sindri'},
            {'name': 'IIM Ranchi', 'url': 'https://iimranchi.ac.in/', 'method': 'iim_ranchi'},
            
            # PSUs - Coal, Steel, Mining
            {'name': 'SAIL', 'url': 'https://www.sail.co.in/en/tenders', 'method': 'sail'},
            {'name': 'Coal India', 'url': 'https://www.coalindia.in/en-us/tenders.aspx', 'method': 'coal_india'},
            {'name': 'Central Coalfields', 'url': 'https://www.centralcoalfields.in/tenders.aspx', 'method': 'central_coal'},
            {'name': 'BCCL', 'url': 'https://www.bcclweb.in/tenders.html', 'method': 'bccl'},
            {'name': 'Eastern Coal', 'url': 'https://www.easterncoal.gov.in/', 'method': 'eastern_coal'},
            {'name': 'MECON', 'url': 'https://www.meconlimited.co.in/', 'method': 'mecon'},
            {'name': 'Hindustan Steel', 'url': 'https://www.hscl.co.in/', 'method': 'hscl'},
            {'name': 'HEC', 'url': 'https://www.hecltd.com/', 'method': 'hec'},
            {'name': 'NSPCL', 'url': 'https://www.nspcl.co.in/tenders', 'method': 'nspcl'},
            {'name': 'Tata Steel', 'url': 'https://www.tatasteel.com/suppliers/', 'method': 'tata_steel'},
            {'name': 'DVC', 'url': 'https://www.dvc.gov.in/tenders', 'method': 'dvc'},
            
            # PSUs - Power, Energy, Oil & Gas
            {'name': 'NTPC', 'url': 'https://ntpctender.ntpc.co.in/', 'method': 'ntpc'},
            {'name': 'NMDC', 'url': 'https://nmdcportals.nmdc.co.in/nmdctender', 'method': 'nmdc'},
            {'name': 'BHEL', 'url': 'https://www.bhel.com/eprocurement/', 'method': 'bhel'},
            {'name': 'GAIL', 'url': 'https://www.gailonline.com/final_website/pagecontent.php?pageid=tenders', 'method': 'gail'},
            {'name': 'SECI', 'url': 'https://www.seci.co.in/show_tenders.php', 'method': 'seci'},
            {'name': 'IOCL', 'url': 'https://iocletenders.nic.in/', 'method': 'iocl'},
            {'name': 'BPCL', 'url': 'https://bpcltenders.eproc.in/', 'method': 'bpcl'},
            {'name': 'ONGC', 'url': 'https://tender.ongcindia.com/', 'method': 'ongc'},
            {'name': 'HPCL', 'url': 'https://hpcltenders.hpcl.co.in/', 'method': 'hpcl'},
            
            # PSUs - Telecom, IT, Construction
            {'name': 'BSNL', 'url': 'https://tender.bsnl.co.in/', 'method': 'bsnl'},
            {'name': 'Bharat Broadband', 'url': 'https://bbnl.nic.in/Tenderarchive.aspx', 'method': 'bbnl'},
            {'name': 'NBCC', 'url': 'https://www.nbccindia.com/tenders', 'method': 'nbcc'},
            {'name': 'TCIL', 'url': 'https://www.tcil-india.com/new/tender/', 'method': 'tcil'},
            
            # Roads, Highways & Rural Development
            {'name': 'PMGSY Bihar', 'url': 'https://www.pmgsytendersbih.gov.in/', 'method': 'pmgsy_bihar'},
            {'name': 'NHAI', 'url': 'https://www.nhai.gov.in/en/tenders', 'method': 'nhai'},
            {'name': 'MoRTH', 'url': 'https://morth.nic.in/', 'method': 'morth'},
            {'name': 'NHIDCL', 'url': 'https://nhidcl.com/tenders/', 'method': 'nhidcl'},
            
            # Urban Development / Smart City / Municipal
            {'name': 'Smart Cities Mission', 'url': 'https://smartcities.gov.in/', 'method': 'smart_cities'},
            
            # Defence / Paramilitary / BRO / MES
            {'name': 'MES', 'url': 'https://mes.gov.in/', 'method': 'mes'},
            {'name': 'BRO', 'url': 'https://bro.gov.in/content/tenders', 'method': 'bro'},
            
            # Central Govt Ministries & Schemes
            {'name': 'MoHUA', 'url': 'https://mohua.gov.in/', 'method': 'mohua'},
            {'name': 'Jal Shakti', 'url': 'https://jalshakti-dowr.gov.in/tenders', 'method': 'jal_shakti'},
            {'name': 'Jal Jeevan Mission', 'url': 'https://jjm.gov.in/', 'method': 'jjm'},
            {'name': 'NHM', 'url': 'https://nhm.gov.in/', 'method': 'nhm'},
            {'name': 'MoSPI', 'url': 'https://mospi.gov.in/tenders', 'method': 'mospi'},
            {'name': 'NITI Aayog', 'url': 'https://niti.gov.in/', 'method': 'niti'},
            {'name': 'FCI', 'url': 'https://fci.gov.in/app2/tenders.php', 'method': 'fci'},
            {'name': 'NABARD', 'url': 'https://www.nabard.org/tenders.aspx', 'method': 'nabard'},
            {'name': 'SIDBI', 'url': 'https://sidbi.in/tenders.aspx', 'method': 'sidbi'},
            
            # Tender Aggregator Portals
            {'name': 'Tenders On Time Bihar', 'url': 'https://www.tendersontime.com/india/bihar-tenders/', 'method': 'tenders_on_time_bihar'},
            {'name': 'Tenders On Time Jharkhand', 'url': 'https://www.tendersontime.com/india/jharkhand-tenders/', 'method': 'tenders_on_time_jharkhand'},
            {'name': 'Tender Detail Bihar', 'url': 'https://www.tenderdetail.com/State-tenders/bihar-tenders', 'method': 'tender_detail_bihar'},
            {'name': 'Tender Detail Jharkhand', 'url': 'https://www.tenderdetail.com/State-tenders/jharkhand-tenders', 'method': 'tender_detail_jharkhand'},
            {'name': 'Tenders Plus Bihar', 'url': 'https://tendersplus.com/bihar-tenders/active', 'method': 'tenders_plus_bihar'},
            {'name': 'Tenders Plus Jharkhand', 'url': 'https://tendersplus.com/jharkhand-tenders/active', 'method': 'tenders_plus_jharkhand'},
            {'name': 'Bid Assist Bihar', 'url': 'https://bidassist.com/bihar-tenders/active', 'method': 'bid_assist_bihar'},
            {'name': 'Bid Assist Jharkhand', 'url': 'https://bidassist.com/jharkhand-tenders/active', 'method': 'bid_assist_jharkhand'},
            {'name': 'Tender247 Bihar', 'url': 'https://www.tender247.com/state/bihar+tenders', 'method': 'tender247_bihar'},
            {'name': 'Tender247 Jharkhand', 'url': 'https://www.tender247.com/state/jharkhand+tenders', 'method': 'tender247_jharkhand'},
            {'name': 'Tenders Shark Bihar', 'url': 'https://www.tendershark.com/tenders/bihar', 'method': 'tenders_shark_bihar'},
            {'name': 'Tenders Shark Jharkhand', 'url': 'https://www.tendershark.com/tenders/jharkhand', 'method': 'tenders_shark_jharkhand'},
            {'name': 'Bihar Tenders', 'url': 'https://www.bihar-tenders.co.in/', 'method': 'bihar_tenders'},
            {'name': 'Jharkhand Tenders', 'url': 'https://www.jharkhandtenders.in/', 'method': 'jharkhand_tenders_site'},
            {'name': 'Tender Bihar', 'url': 'https://tenderbihar.com/', 'method': 'tender_bihar'},
            {'name': 'Bihar Tenders Site', 'url': 'https://www.bihartenders.com/', 'method': 'bihar_tenders_com'},
            {'name': 'The Tenders Bihar', 'url': 'https://www.thetenders.com/state-government/bihar-tenders-notice.html', 'method': 'the_tenders_bihar'},
            {'name': 'Tender18 Bihar', 'url': 'https://tender18.com/all-india-tenders/state-tenders/bihar-tenders', 'method': 'tender18_bihar'},
            {'name': 'Gem Tech Paras Jharkhand', 'url': 'https://gemtechparas.com/govt-tenders/jharkhand-tenders', 'method': 'gem_tech_paras_jharkhand'},
            {'name': 'Tenders Info', 'url': 'https://www.tendersinfo.com/', 'method': 'tenders_info'},
        ]
        
        # Retry settings
        self.max_retries = int(os.getenv('RETRY_ATTEMPTS', 3))
        self.timeout = int(os.getenv('REQUEST_TIMEOUT', 30))
        self.delay_between_requests = 1  # seconds between requests to avoid rate limits

    def fetch_all(self, sources=None):
        """
        Fetch tenders from all configured sources
        """
        logger.info("Starting fetch operation...")
        
        # If specific sources are provided, only fetch from those
        if sources:
            sources_to_fetch = [s for s in self.sources if s['name'] in sources]
        else:
            sources_to_fetch = self.sources
            
        success_count = 0
        error_count = 0
        total_processed = 0
        
        # Create fetch log entry
        log_entry = FetchLog(
            source_portal='ALL_SOURCES',
            success_count=0,
            error_count=0,
            total_processed=0,
            start_time=datetime.utcnow()
        )
        db.session.add(log_entry)
        db.session.commit()
        
        # Process each source with thread pool for efficiency
        with ThreadPoolExecutor(max_workers=min(len(sources_to_fetch), 10)) as executor:
            futures = []
            for source in sources_to_fetch:
                future = executor.submit(self._fetch_from_source, source)
                futures.append((future, source['name']))
                
            for future, source_name in futures:
                try:
                    result = future.result(timeout=120)  # 2 minute timeout per source
                    if result['success']:
                        success_count += result['count']
                        total_processed += result['count']
                        logger.info(f"Successfully fetched {result['count']} tenders from {source_name}")
                    else:
                        error_count += 1
                        total_processed += 1
                        logger.error(f"Error fetching from {source_name}: {result['error']}")
                        
                except Exception as e:
                    error_count += 1
                    total_processed += 1
                    logger.error(f"Exception fetching from {source_name}: {str(e)}")
        
        # Update log entry
        log_entry.success_count = success_count
        log_entry.error_count = error_count
        log_entry.total_processed = total_processed
        log_entry.end_time = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Fetch operation completed. Success: {success_count}, Errors: {error_count}")
        return {'success_count': success_count, 'error_count': error_count}

    def _fetch_from_source(self, source):
        """
        Fetch tenders from a specific source
        """
        method_name = f"_fetch_from_{source['method']}"
        
        if hasattr(self, method_name):
            try:
                # Add delay to avoid rate limiting
                time.sleep(self.delay_between_requests)
                
                # Get the method and call it
                fetch_method = getattr(self, method_name)
                tenders = fetch_method(source['url'])
                
                # Process and save tenders
                saved_count = self._save_tenders(tenders, source['name'])
                
                return {'success': True, 'count': saved_count, 'error': None}
            except Exception as e:
                logger.error(f"Error fetching from {source['name']}: {str(e)}")
                return {'success': False, 'count': 0, 'error': str(e)}
        else:
            # Generic method for sources without specific handler
            try:
                tenders = self._fetch_generic(source['url'])
                saved_count = self._save_tenders(tenders, source['name'])
                return {'success': True, 'count': saved_count, 'error': None}
            except Exception as e:
                logger.error(f"Error fetching from {source['name']}: {str(e)}")
                return {'success': False, 'count': 0, 'error': str(e)}

    def _fetch_generic(self, url):
        """
        Generic method to fetch tenders from any URL
        """
        tenders = []
        
        try:
            # First try with regular requests
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for common tender patterns in the page
            tender_elements = self._find_tender_elements(soup, url)
            
            for element in tender_elements:
                tender_data = self._extract_tender_data(element, url)
                if tender_data:
                    tenders.append(tender_data)
                    
        except requests.RequestException as e:
            logger.warning(f"Regular request failed for {url}, trying with Playwright: {str(e)}")
            # Fallback to Playwright for JavaScript-heavy sites
            tenders.extend(self._fetch_with_playwright(url))
        except Exception as e:
            logger.error(f"Unexpected error fetching from {url}: {str(e)}")
            
        return tenders

    def _find_tender_elements(self, soup, base_url):
        """
        Find tender elements on a page using common selectors
        """
        elements = []
        
        # Common selectors for tender listings
        selectors = [
            '[class*="tender"], [class*="Tender"], [class*="notice"], [class*="Notice"]',
            'a[href*="tender"], a[href*="Tender"], a[href*="notice"], a[href*="Notice"]',
            '.listing-item, .post-item, .article-item',
            'tr',  # Table rows often contain tenders
            '.card, .panel'  # Common card/panel layouts
        ]
        
        for selector in selectors:
            found_elements = soup.select(selector)
            elements.extend(found_elements)
            
        return elements

    def _extract_tender_data(self, element, base_url):
        """
        Extract tender data from an HTML element
        """
        try:
            # Try to extract common fields
            title_elem = element.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a', 'div', 'span'])
            if title_elem:
                title = title_elem.get_text(strip=True)
            else:
                title = element.get_text(strip=True)[:100]  # First 100 chars as title
                
            # Find related links
            link_elem = element.find('a')
            if link_elem and link_elem.get('href'):
                source_url = urljoin(base_url, link_elem.get('href'))
            else:
                source_url = base_url
                
            # Look for dates
            date_text = element.get_text()
            publish_date = self._extract_date(date_text)
            
            # Determine state based on URL
            state = 'Bihar' if 'bihar' in base_url.lower() else 'Jharkhand' if 'jharkhand' in base_url.lower() else 'Unknown'
            
            # Create tender data
            tender_data = {
                'title': title[:500],  # Limit title length
                'source_url': source_url,
                'source_portal': urlparse(base_url).netloc,
                'publish_date': publish_date,
                'state': state,
                'description': element.get_text(strip=True)[:1000],  # Limit description
                'last_checked': datetime.utcnow()
            }
            
            return tender_data
            
        except Exception as e:
            logger.warning(f"Could not extract tender data from element: {str(e)}")
            return None

    def _extract_date(self, text):
        """
        Extract date from text using regex patterns
        """
        # Common date patterns
        patterns = [
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',  # DD/MM/YYYY or MM/DD/YYYY
            r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})',     # YYYY/MM/DD
            r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})',  # DD Month YYYY
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    date_str = match.group(1)
                    # Try different parsing formats
                    for fmt in ['%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d', '%d-%m-%Y', '%m-%d-%Y', '%Y-%m-%d', '%d %B %Y', '%d %b %Y']:
                        try:
                            return datetime.strptime(date_str, fmt)
                        except ValueError:
                            continue
                except:
                    continue
                    
        return None

    def _fetch_with_playwright(self, url):
        """
        Fetch content using Playwright for JavaScript-heavy sites
        """
        tenders = []
        
        try:
            with sync_playwright() as p:
                # Launch browser with stealth settings
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-setuid-sandbox'
                    ]
                )
                
                context = browser.new_context(
                    user_agent=self.ua.random,
                    viewport={'width': 1920, 'height': 1080},
                    extra_http_headers={
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
                    }
                )
                
                page = context.new_page()
                
                # Navigate to the page
                page.goto(url, wait_until='networkidle', timeout=30000)
                
                # Wait for content to load
                page.wait_for_timeout(5000)
                
                # Get page content
                content = page.content()
                
                # Parse with BeautifulSoup
                soup = BeautifulSoup(content, 'html.parser')
                
                # Extract tenders as usual
                tender_elements = self._find_tender_elements(soup, url)
                
                for element in tender_elements:
                    tender_data = self._extract_tender_data(element, url)
                    if tender_data:
                        tenders.append(tender_data)
                
                browser.close()
                
        except Exception as e:
            logger.error(f"Playwright fetch failed for {url}: {str(e)}")
            
        return tenders

    def _save_tenders(self, tenders, source_name):
        """
        Save fetched tenders to the database with deduplication
        """
        saved_count = 0
        
        for tender_data in tenders:
            try:
                # Basic validation
                if not tender_data.get('title') or not tender_data.get('source_url'):
                    continue
                    
                # Check for duplicates based on source_url and title
                existing_tender = Tender.query.filter_by(
                    source_url=tender_data['source_url']
                ).first()
                
                if existing_tender:
                    # Update existing tender if newer information is available
                    existing_tender.last_checked = datetime.utcnow()
                    existing_tender.updated_at = datetime.utcnow()
                else:
                    # Create new tender
                    tender = Tender(
                        title=tender_data.get('title', '')[:500],
                        description=tender_data.get('description', '')[:1000],
                        source_portal=source_name,
                        source_url=tender_data.get('source_url', ''),
                        publish_date=tender_data.get('publish_date'),
                        state=tender_data.get('state', 'Unknown'),
                        last_checked=datetime.utcnow(),
                        verification_score=50  # Default score
                    )
                    
                    db.session.add(tender)
                    
                saved_count += 1
                
            except Exception as e:
                logger.error(f"Error saving tender: {str(e)}")
                continue
                
        # Commit all changes at once for efficiency
        try:
            db.session.commit()
        except Exception as e:
            logger.error(f"Error committing tenders to database: {str(e)}")
            db.session.rollback()
            
        return saved_count

    # Specific fetch methods for different portals
    def _fetch_from_gem(self, url):
        """Fetch from Government e-Marketplace (GEM)"""
        # Implementation for GEM portal
        tenders = []
        try:
            # GEM has an API we can use
            api_url = "https://gem.gov.in/api/public/tenders"
            response = self.session.get(api_url, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                for item in data.get('data', []):
                    if any(state in item.get('location', '').lower() for state in ['bihar', 'jharkhand']):
                        tenders.append({
                            'title': item.get('title', ''),
                            'description': item.get('description', ''),
                            'source_url': item.get('tender_url', ''),
                            'source_portal': 'GEM',
                            'publish_date': datetime.strptime(item.get('publish_date', ''), '%Y-%m-%d') if item.get('publish_date') else None,
                            'state': 'Bihar' if 'bihar' in item.get('location', '').lower() else 'Jharkhand',
                            'last_checked': datetime.utcnow()
                        })
        except Exception as e:
            logger.error(f"GEM fetch error: {str(e)}")
        return tenders

    def _fetch_from_eprocure(self, url):
        """Fetch from eProcure portal"""
        tenders = []
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for tender listings on the page
            tender_items = soup.find_all('div', class_='tender-item') or soup.find_all('tr', class_='tender-row')
            
            for item in tender_items:
                title_elem = item.find(['h3', 'h4', 'a', 'td'])
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    link_elem = title_elem.find('a') if title_elem.name != 'a' else title_elem
                    link = link_elem.get('href') if link_elem else None
                    
                    if link:
                        source_url = urljoin(url, link)
                        tenders.append({
                            'title': title[:500],
                            'source_url': source_url,
                            'source_portal': 'eProcure',
                            'state': 'Central'  # Central government portal
                        })
        except Exception as e:
            logger.error(f"eProcure fetch error: {str(e)}")
        return tenders

    def _fetch_from_bihar_eproc2(self, url):
        """Fetch from Bihar eProc2 portal"""
        tenders = []
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for tender listings
            tender_elements = soup.find_all('tr', class_='tender-row') or soup.find_all('div', class_='tender-item')
            
            for element in tender_elements:
                cells = element.find_all(['td', 'div'])
                if len(cells) >= 2:
                    title = cells[0].get_text(strip=True)
                    link_elem = cells[0].find('a')
                    if link_elem and link_elem.get('href'):
                        source_url = urljoin(url, link_elem.get('href'))
                        tenders.append({
                            'title': title[:500],
                            'source_url': source_url,
                            'source_portal': 'Bihar eProc2',
                            'state': 'Bihar'
                        })
        except Exception as e:
            logger.error(f"Bihar eProc2 fetch error: {str(e)}")
        return tenders

    def _fetch_from_jharkhand_tenders(self, url):
        """Fetch from Jharkhand Tenders portal"""
        tenders = []
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for tender listings
            tender_elements = soup.find_all('div', class_='tender-list-item') or soup.find_all('tr')
            
            for element in tender_elements:
                title_elem = element.find(['h3', 'h4', 'a', 'td'])
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    link_elem = title_elem.find('a')
                    if link_elem and link_elem.get('href'):
                        source_url = urljoin(url, link_elem.get('href'))
                        tenders.append({
                            'title': title[:500],
                            'source_url': source_url,
                            'source_portal': 'Jharkhand Tenders',
                            'state': 'Jharkhand'
                        })
        except Exception as e:
            logger.error(f"Jharkhand Tenders fetch error: {str(e)}")
        return tenders

    # Add more specific fetch methods as needed for other portals...