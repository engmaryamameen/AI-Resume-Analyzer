import io
import os
import re
import nltk
import pandas as pd
import docx2txt
import spacy
from datetime import datetime
from dateutil import relativedelta
from pdfminer.converter import TextConverter
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFSyntaxError
from nltk.stem import WordNetLemmatizer
from nltk.corpus import stopwords


RESUME_SECTIONS_GRAD = [
    'accomplishments',
    'experience',
    'education',
    'interests',
    'projects',
    'professional experience',
    'publications',
    'skills',
    'certifications',
    'objective',
    'career objective',
    'summary',
    'leadership'
]

RESUME_SECTIONS_PROFESSIONAL = [
    'experience',
    'education',
    'interests',
    'professional experience',
    'publications',
    'skills',
    'certifications',
    'objective',
    'career objective',
    'summary',
    'leadership'
]

EDUCATION = [
    'BE', 'B.E.', 'B.E', 'BS', 'B.S', 'ME', 'M.E',
    'M.E.', 'MS', 'M.S', 'BTECH', 'MTECH',
    'SSC', 'HSC', 'CBSE', 'ICSE', 'X', 'XII'
]

YEAR = r'(((20|19)(\d{2})))'
STOPWORDS = set(stopwords.words('english'))


def extract_text_from_pdf(pdf_path):
    if not isinstance(pdf_path, io.BytesIO):
        with open(pdf_path, 'rb') as fh:
            try:
                for page in PDFPage.get_pages(fh, caching=True, check_extractable=True):
                    resource_manager = PDFResourceManager()
                    fake_file_handle = io.StringIO()
                    converter = TextConverter(resource_manager, fake_file_handle, codec='utf-8', laparams=LAParams())
                    page_interpreter = PDFPageInterpreter(resource_manager, converter)
                    page_interpreter.process_page(page)
                    text = fake_file_handle.getvalue()
                    yield text
                    converter.close()
                    fake_file_handle.close()
            except PDFSyntaxError:
                return
    else:
        try:
            for page in PDFPage.get_pages(pdf_path, caching=True, check_extractable=True):
                resource_manager = PDFResourceManager()
                fake_file_handle = io.StringIO()
                converter = TextConverter(resource_manager, fake_file_handle, codec='utf-8', laparams=LAParams())
                page_interpreter = PDFPageInterpreter(resource_manager, converter)
                page_interpreter.process_page(page)
                text = fake_file_handle.getvalue()
                yield text
                converter.close()
                fake_file_handle.close()
        except PDFSyntaxError:
            return


def get_number_of_pages(file_name):
    try:
        if isinstance(file_name, io.BytesIO):
            count = 0
            for page in PDFPage.get_pages(file_name, caching=True, check_extractable=True):
                count += 1
            return count
        else:
            if file_name.endswith('.pdf'):
                count = 0
                with open(file_name, 'rb') as fh:
                    for page in PDFPage.get_pages(fh, caching=True, check_extractable=True):
                        count += 1
                return count
            else:
                return None
    except PDFSyntaxError:
        return None


def extract_text_from_docx(doc_path):
    try:
        temp = docx2txt.process(doc_path)
        text = [line.replace('\t', ' ') for line in temp.split('\n') if line]
        return ' '.join(text)
    except KeyError:
        return ' '


def extract_text_from_doc(doc_path):
    try:
        try:
            import textract
        except ImportError:
            return ' '
        text = textract.process(doc_path).decode('utf-8')
        return text
    except KeyError:
        return ' '


def extract_text(file_path, extension):
    text = ''
    if extension == '.pdf':
        for page in extract_text_from_pdf(file_path):
            text += ' ' + page
    elif extension == '.docx':
        text = extract_text_from_docx(file_path)
    elif extension == '.doc':
        text = extract_text_from_doc(file_path)
    return text


def extract_entity_sections_grad(text):
    text_split = [i.strip() for i in text.split('\n')]
    entities = {}
    key = False
    for phrase in text_split:
        if len(phrase) == 1:
            p_key = phrase
        else:
            p_key = set(phrase.lower().split()) & set(RESUME_SECTIONS_GRAD)
        try:
            p_key = list(p_key)[0]
        except IndexError:
            pass
        if p_key in RESUME_SECTIONS_GRAD:
            entities[p_key] = []
            key = p_key
        elif key and phrase.strip():
            entities[key].append(phrase)
    return entities


def extract_entities_wih_custom_model(custom_nlp_text):
    entities = {}
    for ent in custom_nlp_text.ents:
        if ent.label_ not in entities.keys():
            entities[ent.label_] = [ent.text]
        else:
            entities[ent.label_].append(ent.text)
    for key in entities.keys():
        entities[key] = list(set(entities[key]))
    return entities


def extract_email(text):
    email = re.findall(r"([^@|\s]+@[^@]+\.[^@|\s]+)", text)
    if email:
        try:
            return email[0].split()[0].strip(';')
        except IndexError:
            return None


def extract_name(nlp_text, matcher):
    """
    Improved name extraction with multiple fallback strategies
    """
    text = nlp_text.text
    import re
    
    # Strategy 1: Look for all-caps name near email
    # Pattern: All caps name (2-3 words) followed by location/email pattern
    email_pattern = r'([A-Z]{2,}\s+[A-Z]{2,}(?:\s+[A-Z]{2,})?)[A-Z][a-z]+.*?[\w\.-]+@[\w\.-]+'
    email_match = re.search(email_pattern, text)
    if email_match:
        potential_name = email_match.group(1).strip()
        words = potential_name.split()
        if len(words) >= 2 and len(words) <= 4:
            # Check it's not a section header
            exclude_words = {'SOFTWARE', 'ENGINEER', 'ENGENIER', 'PROFESSIONAL', 'TECHNICAL', 
                           'SKILLS', 'EXPERIENCE', 'EDUCATION', 'INFORMATION'}
            if not any(word in exclude_words for word in words):
                return potential_name
    
    # Strategy 2: Look for 2-word all-caps pattern (exact match, most names)
    two_word_caps = r'([A-Z]{2,}\s+[A-Z]{2,})'
    two_word_matches = re.findall(two_word_caps, text)
    
    exclude_words = {'SUMMARY', 'SKILLS', 'EXPERIENCE', 'EDUCATION', 'PROFESSIONAL', 
                     'TECHNICAL', 'ADDITIONAL', 'INFORMATION', 'CERTIFICATIONS',
                     'PROJECTS', 'REFERENCES', 'OBJECTIVE', 'PROFILE', 'CONTACT',
                     'SOFTWARE', 'ENGINEER', 'ENGENIER', 'DESIGNER', 'DEVELOPER', 'MANAGER',
                     'ANALYST', 'SPECIALIST', 'CONSULTANT', 'COORDINATOR'}
    
    for caps_name in two_word_matches:
        words = caps_name.split()
        if len(words) == 2:
            if not any(word in exclude_words for word in words):
                return caps_name
    
    # Strategy 3: Pattern matching with spaCy
    patterns = [
        [{'POS': 'PROPN'}, {'POS': 'PROPN'}, {'POS': 'PROPN'}],
        [{'POS': 'PROPN'}, {'POS': 'PROPN'}],
    ]
    
    for pattern_idx, pattern in enumerate(patterns):
        matcher.add(f'NAME_{pattern_idx}', [pattern])
    
    matches = matcher(nlp_text)
    
    valid_names = []
    common_words = {'resume', 'cv', 'curriculum', 'vitae', 'name', 'contact', 'phone', 'email', 
                    'address', 'objective', 'summary', 'education', 'experience', 'skills',
                    'projects', 'certifications', 'references', 'portfolio', 'profile',
                    'professional', 'design', 'engineer', 'license', 'project', 'management',
                    'tech', 'awards', 'activities', 'bachelor', 'master', 'university',
                    'college', 'school', 'degree', 'certification'}
    
    for match_id, start, end in matches:
        span = nlp_text[start:end]
        name_text = span.text.strip()
        name_lower = name_text.lower()
        
        if name_lower and not any(word in name_lower for word in common_words):
            if len(name_text.split()) >= 2 and len(name_text.split()) <= 4:
                valid_names.append((name_text, start, len(name_text.split())))
    
    if valid_names:
        valid_names.sort(key=lambda x: (x[1], -x[2]))
        return valid_names[0][0]
    
    # Strategy 4: spaCy NER entities
    for ent in nlp_text.ents:
        if ent.label_ == 'PERSON':
            name_text = ent.text.strip()
            words = name_text.split()
            if len(words) >= 2 and len(words) <= 4:
                if not any(word.lower() in common_words for word in words):
                    return name_text
    
    return None


def extract_mobile_number(text, custom_regex=None):
    if not custom_regex:
        mob_num_regex = r'''(\d{3}[-\.\s]??\d{3}[-\.\s]??\d{4}|\(\d{3}\)
                        [-\.\s]*\d{3}[-\.\s]??\d{4}|\d{3}[-\.\s]??\d{4})'''
        phone = re.findall(re.compile(mob_num_regex), text)
    else:
        phone = re.findall(re.compile(custom_regex), text)
    if phone:
        number = ''.join(phone[0])
        return number


def extract_skills(nlp_text, noun_chunks, skills_file=None):
    tokens = [token.text for token in nlp_text if not token.is_stop]
    if not skills_file:
        data = pd.read_csv(os.path.join(os.path.dirname(__file__), 'skills.csv'))
    else:
        data = pd.read_csv(skills_file)
    skills = list(data.columns.values)
    skillset = []
    
    for token in tokens:
        if token.lower() in skills:
            skillset.append(token)
    
    for token in noun_chunks:
        token = token.text.lower().strip()
        if token in skills:
            skillset.append(token)
    
    return [i.capitalize() for i in set([i.lower() for i in skillset])]


def extract_education(nlp_text):
    edu = {}
    try:
        for index, text in enumerate(nlp_text):
            for tex in text.split():
                tex = re.sub(r'[?|$|.|!|,]', r'', tex)
                if tex.upper() in EDUCATION and tex not in STOPWORDS:
                    edu[tex] = text + nlp_text[index + 1]
    except IndexError:
        pass
    
    education = []
    for key in edu.keys():
        year = re.search(re.compile(YEAR), edu[key])
        if year:
            education.append((key, ''.join(year.group(0))))
        else:
            education.append(key)
    return education
