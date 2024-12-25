from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
import pandas as pd
import random
import time
from datetime import datetime
import os
import json
import re

class ValidationResults:
    def __init__(self):
        self.incorrect_answers = []
        self.total_questions = 0
        self.incorrect_count = 0

    def add_result(self, number, structure, operation, question, response, reason):
        """Add an incorrect result to the tracking"""
        self.total_questions += 1
        if not operation:  # If validation failed
            self.incorrect_count += 1
            self.incorrect_answers.append({
                'number': number,
                'structure': structure,
                'question': question,
                'response': response,
                'reason': reason
            })

    def display_results(self):
        """Display validation results with details of incorrect answers"""
        print("\n=== Validation Results ===")
        print(f"Total questions: {self.total_questions}")
        print(f"Incorrect answers: {self.incorrect_count}")
        print(f"Success rate: {((self.total_questions - self.incorrect_count)/self.total_questions)*100:.2f}%")
        
        if self.incorrect_answers:
            print("\nIncorrect Answers:")
            for item in self.incorrect_answers:
                print(f"\n{item['number']}. Structure: {item['structure']}")
                print(f"Question: {item['question']}")
                print(f"Response received:")
                print(f"{item['response'][:200]}...")  # Show first 200 chars of response
                print(f"Reason incorrect: {item['reason']}")
                print("-" * 80)

class DataStructureValidator:
    def __init__(self):
        self.state = {
            'graph': {'nodes': set(), 'edges': set()},
            'tree': {'nodes': set(), 'root': None},
            'linked_list': {'values': []},
            'queue': {'values': []}
        }
        self.initial_values = []

    def update_initial_values(self, values):
        """Store initial values used to create structures"""
        self.initial_values = values
        # Initialize structures with these values
        self.state['graph']['nodes'] = set(values)
        self.state['graph']['edges'] = {(values[i], values[i+1]) for i in range(len(values)-1)}
        self.state['tree']['nodes'] = set(values)
        self.state['tree']['root'] = values[0]
        self.state['linked_list']['values'] = values.copy()
        self.state['queue']['values'] = values.copy()

    def clean_json(self, response):
        """Extract and parse JSON from ChatGPT response"""
        try:
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end != 0:
                json_str = response[start:end]
                return json.loads(json_str)
        except:
            return None

    def validate_graph_operation(self, operation, values, response):
        """Validate graph operations"""
        json_resp = self.clean_json(response)
        if not json_resp:
            return False, "Invalid JSON response"

        if 'Insert' in operation:
            # Check if new edge between existing nodes is properly added
            node1, node2 = values
            if node1 in self.state['graph']['nodes'] and node2 in self.state['graph']['nodes']:
                edges = set()
                if 'edges' in str(json_resp):
                    current_edges = json_resp.get('graphUpdate', {}).get('edges', [])
                    return (node1, node2) in {(e['from'], e['to']) for e in current_edges}, "Edge not properly added"
            elif node1 == node2:
                return 'error' in str(json_resp).lower(), "Should indicate self-loop not allowed"

        elif 'Delete' in operation:
            if 'message' in str(json_resp) and 'not exist' in str(json_resp).lower():
                return True, "Correctly handled non-existent node"
            return values[0] not in self.state['graph']['nodes'], "Incorrect deletion response"

        elif 'Check' in operation or 'path' in operation.lower():
            return 'pathExists' in str(json_resp), "Missing path check result"

        return True, "Operation appears valid"

    def validate_tree_operation(self, operation, values, response):
        """Validate BST operations"""
        json_resp = self.clean_json(response)
        if not json_resp:
            return False, "Invalid JSON response"

        if 'Search' in operation or 'Find' in operation:
            target = values[0]
            found = 'found' in str(json_resp).lower() and 'true' in str(json_resp).lower()
            should_exist = target in self.state['tree']['nodes']
            return found == should_exist, "Search result incorrect"

        elif 'Insert' in operation:
            if values[0] in self.state['tree']['nodes']:
                return 'error' in str(json_resp).lower(), "Should indicate duplicate value"
            return 'structure' in str(json_resp), "Missing updated tree structure"

        elif 'Delete' in operation:
            target = values[0]
            if target not in self.state['tree']['nodes']:
                return 'not found' in str(json_resp).lower(), "Should indicate non-existent value"
            return 'structure' in str(json_resp), "Missing updated tree structure"

        return True, "Operation appears valid"

    def validate_linked_list_operation(self, operation, values, response):
        """Validate linked list operations"""
        json_resp = self.clean_json(response)
        if not json_resp:
            return False, "Invalid JSON response"

        if 'Insert' in operation:
            # Handle position-based insertion
            if 'position' in operation.lower():
                position = values[0]
                if position >= len(self.state['linked_list']['values']):
                    return 'out of bounds' in str(json_resp).lower(), "Should indicate out of bounds"
            return 'structure' in str(json_resp), "Missing updated list structure"

        elif 'Delete' in operation:
            if 'position' in operation.lower():
                position = values[0]
                if position >= len(self.state['linked_list']['values']):
                    return 'out of bounds' in str(json_resp).lower(), "Should indicate out of bounds"
            return 'structure' in str(json_resp), "Missing updated list structure"

        elif 'Update' in operation:
            if 'position' in operation.lower():
                position = values[0]
                if position >= len(self.state['linked_list']['values']):
                    return 'out of bounds' in str(json_resp).lower(), "Should indicate out of bounds"
            return 'structure' in str(json_resp), "Missing updated list structure"

        return True, "Operation appears valid"

    def validate_queue_operation(self, operation, response):
        """Validate queue operations"""
        json_resp = self.clean_json(response)
        if not json_resp:
            return False, "Invalid JSON response"

        if 'Dequeue' in operation:
            if len(self.state['queue']['values']) == 0:
                return 'empty' in str(json_resp).lower(), "Should indicate empty queue"
            return 'dequeuedValue' in str(json_resp), "Missing dequeued value"

        elif 'Enqueue' in operation:
            return 'updatedQueue' in str(json_resp), "Missing updated queue state"

        elif 'Display' in operation:
            return 'queue' in str(json_resp).lower(), "Missing queue contents"

        elif 'Check' in operation or 'exists' in operation.lower():
            return 'exists' in str(json_resp).lower(), "Missing existence check result"

        return True, "Operation appears valid"

    def validate_response(self, structure, operation, values, response):
        """Main validation method"""
        if structure == 'graph':
            return self.validate_graph_operation(operation, values, response)
        elif structure == 'tree':
            return self.validate_tree_operation(operation, values, response)
        elif structure == 'linked_list':
            return self.validate_linked_list_operation(operation, values, response)
        elif structure == 'queue':
            return self.validate_queue_operation(operation, response)
        return False, "Unknown structure type"

def generate_structured_questions():
    """Generate questions with initial creation and related operations"""
    
    # Generate values that will exist in our structures
    tree_values = random.sample(range(1, 100), 5)
    graph_values = random.sample(range(1, 100), 5)
    linked_list_values = random.sample(range(1, 100), 5)
    queue_values = random.sample(range(1, 100), 5)
    
    non_existing_values = [x for x in range(1, 100) if x not in tree_values + graph_values + linked_list_values + queue_values][:5]
    
    questions = []
    
    # Creation questions (always first)
    creation_questions = {
        # 'tree': f"Create a binary search tree with the following values: {', '.join(map(str, tree_values))}.",
        # 'graph': f"Create a graph with the following nodes: {', '.join(map(str, graph_values))}. Then add random edge weights between consecutive nodes.",
        # 'linked_list': f"Create a linked list with the following values: {', '.join(map(str, linked_list_values))}.",
        'queue': f"Create a queue with the following values: {', '.join(map(str, queue_values))}."
    }
    
    # Add creation questions first
    for structure, question in creation_questions.items():
        questions.append({
            'structure': structure,
            'operation': 'create',
            'question': question,
            'values': eval(f"{structure}_values")
        })
    
    # Testing operations with existing and non-existing values
    operations = {
        'graph': [
            # {'op': 'Update node', 'values': [random.choice(graph_values), random.choice(graph_values), random.randint(1, 10)]},
            # {'op': 'Update node', 'values': [random.choice(graph_values), random.choice(non_existing_values), random.randint(1, 10)]},
            # {'op': 'Insert node', 'values': [random.choice(non_existing_values), random.randint(1, 10)]},
            # {'op': 'Delete node', 'values': [random.choice(graph_values)]},
            # {'op': 'Check path', 'values': [random.choice(graph_values), random.choice(graph_values)]}
        ],
        'tree': [
            # {'op': 'Insert', 'values': [random.choice(non_existing_values)]},
            # {'op': 'Delete', 'values': [random.choice(tree_values)]},
            # {'op': 'Search', 'values': [random.choice(tree_values)]},
            # {'op': 'Search', 'values': [random.choice(non_existing_values)]}
        ],
        'linked_list': [
            # {'op': 'Insert at beginning', 'values': [random.choice(non_existing_values)]},
            # {'op': 'Insert at end', 'values': [random.choice(non_existing_values)]},
            # {'op': 'Delete from beginning', 'values': []},
            # {'op': 'Delete from end', 'values': []},
            # {'op': 'Delete value', 'values': [random.choice(linked_list_values)]},
            # {'op': 'Search value', 'values': [random.choice(linked_list_values)]}
        ],
        'queue': [
            {'op': 'Enqueue', 'values': [random.choice(non_existing_values)]},
            {'op': 'Dequeue', 'values': [random.choice(non_existing_values)]},
            {'op': 'Check if empty', 'values': []},
            {'op': 'Get front', 'values': []}
        ]
    }
    
    # Add operation questions
    for structure, ops in operations.items():
        for op in ops:
            question = f"For the {structure} created earlier, {op['op']}"
            if op['values']:
                if len(op['values']) == 3:
                    question += f" values {op['values'][0]}, {op['values'][1]}, and edge weight {op['values'][2]}"
                elif len(op['values']) == 2:
                    question += f" value {op['values'][0]} and edge weight {op['values'][1]}"
                else:
                    question += f" value(s) {', '.join(map(str, op['values']))}"
            question += "."
            
            questions.append({
                'structure': structure,
                'operation': op['op'],
                'values': op['values'],
                'question': question
            })
    
    return questions, tree_values, graph_values, linked_list_values, queue_values, non_existing_values

def format_creation_message(questions):
    """Format list of questions as a single message for initial structure creation"""
    creation_questions = [q for q in questions if q['operation'] == 'create']
    message = "Please create all of these data structures:\n\n"
    for q in creation_questions:
        message += f"- {q['question']}\n"
    return message

def send_message(driver, message):
    """Send a message and wait for response, with page refresh after 2 attempts"""
    max_retries = 4
    for attempt in range(max_retries):
        try:
            if attempt == 2:
                print("Refreshing page after 2 failed attempts...")
                driver.refresh()
                time.sleep(5)
                
                initial_request = """For all responses in this conversation, respond in JSON format"""
                textarea = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "prompt-textarea"))
                )
                driver.execute_script("arguments[0].value = '';", textarea)
                textarea.clear()
                textarea.send_keys(initial_request)
                time.sleep(1)
                textarea.send_keys(Keys.RETURN)
                time.sleep(5)
            
            textarea = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "prompt-textarea"))
            )
            
            driver.execute_script("arguments[0].value = '';", textarea)
            textarea.clear()
            textarea.send_keys(message)
            time.sleep(1)
            textarea.send_keys(Keys.RETURN)
            
            print(f"Waiting for response... (Attempt {attempt + 1})")
            time.sleep(5)
            
            for _ in range(5):
                response_elements = driver.find_elements(By.CSS_SELECTOR, ".markdown")
                if response_elements:
                    response_text = response_elements[-1].text
                    if response_text and response_text != "No response found":
                        print("Response found!")
                        return response_text
                time.sleep(2)
            
            print(f"No response found on attempt {attempt + 1}")
                
        except Exception as e:
            print(f"Error on attempt {attempt + 1}: {str(e)}")
            time.sleep(2)
            
    return "No response found after retries"

def automate_chatgpt():
    user_data_dir = os.path.expandvars(r'C:/Users/Darin Tang/AppData/Local/Google/Chrome/User Data')  # Replace with your path
    
    options = webdriver.ChromeOptions()
    options.add_argument(f'--user-data-dir={user_data_dir}')
    options.add_argument('--profile-directory=Default')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.maximize_window()
        
        driver.get("https://chat.openai.com")
        print("Starting message processing...")
        
        # Initialize validator and results tracker
        validator = DataStructureValidator()
        validation_results = ValidationResults()
        
        # Generate questions and get test values
        questions, tree_values, graph_values, linked_list_values, queue_values, non_existing_values = generate_structured_questions()
        
        # Update initial values for each data structure separately
        validator.update_initial_values(tree_values)
        validator.update_initial_values(graph_values)
        validator.update_initial_values(linked_list_values)
        validator.update_initial_values(queue_values)
        
        responses = []
        question_number = 1
        
        # Initial format request
        initial_request = """For all responses in this conversation, respond in JSON format. Don't even try to create a graph using python code"""
        print("\nSending initial format request...")
        send_message(driver, initial_request)
        time.sleep(3)
        
        # Process each question
        for question in questions:
            print(f"\nProcessing question {question_number}/{len(questions)}")
            response = send_message(driver, question['question'])
            
            # Validate response
            valid, reason = validator.validate_response(
                question['structure'],
                question['operation'],
                question.get('values', []),
                response
            )
            
            # Track results
            validation_results.add_result(
                question_number,
                question['structure'],
                valid,
                question['question'],
                response,
                reason
            )
            
            responses.append({
                'number': question_number,
                'structure': question['structure'],
                'operation': question['operation'],
                'question': question['question'],
                'response': response,
                'valid': valid,
                'reason': reason
            })
            
            question_number += 1
            time.sleep(3)
        
        # Save results to CSV
        output_df = pd.DataFrame(responses)
        output_filename = f"chatgpt_responses_validated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        output_df.to_csv(output_filename, index=False)
        print(f"\nResponses saved to: {output_filename}")
        
        # Display validation results
        validation_results.display_results()
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        
    finally:
        if 'driver' in locals():
            driver.quit()

if __name__ == "__main__":
    automate_chatgpt()