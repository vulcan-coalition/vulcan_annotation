import json
import argparse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    

def check_annotation(node, parent_path='', internal_key_counter=0):
    errors = []
    warnings = []
    revised_node = dict()
    
    # first, check if it's a dict in the first place (if not we can't check anything)
    if not isinstance(node, dict):
        if not parent_path:
            errors.append("The input annotation structure is not a dictionary.")
        else:
            errors.append(f"A child node of '{parent_path}' is not a dictionary.")
        return {'errors': errors, 'warnings': warnings, 'revised_node': None, 'internal_key_counter': internal_key_counter}
        
    # check 'key' field
    key_warning = ''; key_has_content = False
    if not 'key' in node:
        internal_key_counter += 1
        key = f'node_{internal_key_counter}'
        if not parent_path:
            key_warning = f"The root node is missing key. Assigning a default key: '{key}'."
        else:
            key_warning = f"A child node of '{parent_path}' is missing key. Assigning a default key: '{key}'."
    else:
        if not isinstance(node['key'], str):
            internal_key_counter += 1
            key = f'node_{internal_key_counter}'
            if not parent_path:
                key_warning = f"The key of the root node is not a string. Assigning a default key: '{key}'."
            else:
                key_warning = f"The key of a child node of '{parent_path}' is not a string. Assigning a default key: '{key}'."
        else:
            key = node['key']
            cleaned_key = ' '.join(''.join(c for c in key if c.isprintable()).replace('\t', ' ').replace('\n', ' ').split())
            if cleaned_key != key:
                if cleaned_key == '':
                    internal_key_counter += 1
                    cleaned_key = f'node_{internal_key_counter}'
                    key_warning = f"The key '{key}' has no content. It has been renamed to '{cleaned_key}'."
                else:
                    key_has_content = True
                    key_warning = f"The key '{key}' has been cleaned to '{cleaned_key}' to remove non-printable characters and extra spaces."
                key = cleaned_key
            else:
                key_has_content = True
    if(not(key_has_content) and not(('description' in node) and isinstance(node['description'], str) and node['description'].strip())):
        key_warning += f" CRITICAL: This node also has no description. Combined with no informative key, it is difficult to understand the purpose of this node."
    if key_warning:
        warnings.append(key_warning)
    revised_node['key'] = key
    full_path = f"{parent_path} -> {key}" if parent_path else f"{key}"
    
    # check 'description' field
    if 'description' in node:
        if not isinstance(node['description'], str):
            warnings.append(f"The node '{key}' has a 'description' field that is not a string. (full path to the node: '{full_path}')")
        else:
            cleaned_description = ' '.join(''.join(c for c in node['description'] if c.isprintable()).replace('\t', ' ').replace('\n', ' ').split())
            if cleaned_description:
                revised_node['description'] = cleaned_description
                
    # check 'metadata' field
    if ('metadata' in node) and node['metadata']:
        revised_node['metadata'] = node['metadata']
    
    # check 'required' field      
    if 'required' in node:
        if not isinstance(node['required'], bool):
            if node['required'] in ['True', 'true', 'Yes', 'yes']:
                warnings.append(f"The node '{key}' has a 'required' field in which its value is not a boolean. Assigning 'required': True. (full path to the node: '{full_path}')")
                required = True
            else:
                warnings.append(f"The node '{key}' has a 'required' field in which its value is not a boolean. As a result, the key 'required' is removed from the node, which means the node is assumed to not be required. (full path to the node: '{full_path}')")
                required = False
        else:
            required = node['required']
    else:
        required = False
    if required:
        revised_node['required'] = True
    
    # recursively check children
    children = []
    if ('choices' in node):
        if isinstance(node['choices'], list):
            for child in node['choices']:
                update = check_annotation(node=child, parent_path=full_path, internal_key_counter=internal_key_counter)
                internal_key_counter = update['internal_key_counter']
                errors += update['errors']
                warnings += update['warnings']
                if update['revised_node'] is not None:
                    children.append(update['revised_node'])
        else: # can't do anything with choices that is not a list
            errors.append(f"The node '{key}' has the field 'choices' that is not a list. As a result, the key 'choices' is removed from the node, which means it is assumed to have no children. (full path to the node: '{full_path}')")       
                
    # all children has valid keys now, rename if it's duplicate with either parent or sibling
    for i in range(len(children)):
        child_key = children[i]['key']
        if ((len([c for c in children if c['key'] == child_key]) > 1) or (child_key == key)):
            # if the key is duplicate with either parent or sibling, rename it
            original_child_key = child_key
            child_key_counter = 1
            child_key = f"{child_key}_{child_key_counter}"
            while(any([c['key'] == child_key for c in children]) or (child_key == key)):
                child_key_counter += 1
                child_key = f"{child_key}_{child_key_counter}"
            if (key == original_child_key):
                warnings.append(f"The node '{key}' has a child with the same key as itself. Renaming the child to '{child_key}'. (full path to the node: '{full_path}')")
            else:
                warnings.append(f"The node '{key}' has a child with the same key as its sibling. Renaming the child from '{original_child_key}' to '{child_key}'. (full path to the node: '{full_path}')")
            children[i]['key'] = child_key  
    
    # check inputType conflicts with children
    if ('inputType' in node):
        if(node['inputType'] in ['mutual', 'multiple', 'text', 'property']):
            input_type = node['inputType']
        else:
            if(children):
                warnings.append(f"The node '{key}' has an invalid inputType. Valid types are 'mutual', 'multiple', 'text', and 'property'. Assigning a default type 'multiple' since it has a child. (full path to the node: '{full_path}')")
                input_type = 'multiple'
            else:
                warnings.append(f"The node '{key}' has an invalid inputType. Valid types are 'mutual', 'multiple', 'text', and 'property'. As a result, the key 'inputType' is removed from the node, which means it is assumed to have boolean value of selected/unselected. (full path to the node: '{full_path}')")
                input_type = 'boolean'
    else:
        input_type = 'boolean'
    if (input_type in ['boolean', 'text']) and children:
        warnings.append(f"The node '{key}' has children but its inputType does not support choices. Valid inputTypes for choices are 'mutual', 'multiple', and 'property'. Assigning a default type 'multiple' since it has a child. (full path to the node: '{full_path}')")
        input_type = 'multiple'
    elif (input_type in ['mutual', 'multiple', 'property']) and not children:
        warnings.append(f"The node '{key}' has inputType '{input_type}' but has no valid child. As a result, the key 'inputType' is removed from the node, which means it is assumed to have boolean value of selected/unselected. (full path to the node: '{full_path}')")
        input_type = 'boolean'
    if not (input_type == 'boolean'):
        revised_node['inputType'] = input_type
    
    # check for requirement conflicts in children   
    for child in children:
        if ('required' in child): # always required=True, we have already checked it
            if input_type == 'mutual': # can't have a required child!
                child_key = child['key']
                warnings.append(f"The node '{key}' has a child '{child_key}' with required=True, which is not allowed when the inputType of '{key}' is 'mutual'. The child will be set to not required. (full path to the node: '{full_path}')")
                del child['required']
            elif input_type == 'property': # all children are required by default, just silently remove the 'required' key
                del child['required']
    if len(children) == 1: # valid, just weird
        warnings.append(f"The node '{key}' has only one child. It is still valid, but it is recommended to have more than one child, or for it and the child to collapse into one node, for more intuitive annotation structure. (full path to the node: '{full_path}')")

    # finally assign children to the revised node
    if children:
        revised_node['choices'] = children
    
    return {'errors': errors, 'warnings': warnings, 'revised_node': revised_node, 'internal_key_counter': internal_key_counter}

def check_annotation_full(input_path=None, output_path=None, error_logging_path=None):
    """
    Check the annotation structure in the input file and return a revised structure.
    
    Parameters:
    - input_path: Path to the input JSON file containing the annotation structure.
    - output_path: Path to save the revised annotation structure (optional).
    - error_logging_path: Path to save errors and warnings (optional).
    """

    # Parse command line arguments if no parameters provided
    if input_path is None:
        parser = argparse.ArgumentParser(description='Check and revise annotation structure')
        parser.add_argument('input_path', help='Path to input JSON file')
        parser.add_argument('--output_path', help='Path to save revised annotation (optional)')
        parser.add_argument('--error_logging_path', help='Path to save errors and warnings (optional)')
        
        args = parser.parse_args()
        input_path = args.input_path
        output_path = args.output_path
        error_logging_path = args.error_logging_path
    
    with open(input_path, 'r', encoding='utf-8') as f:
        data_dict = json.load(f)
    
    if not isinstance(data_dict, dict):
        raise ValueError("The input annotation structure is not a dictionary.")
    
    result = check_annotation(data_dict)
    
    if output_path is None:
        output_path = input_path[:-5] + '_revised.json'
        logging.info(f"No output path provided, saving revised annotation to '{output_path}'")
    if error_logging_path is None:
        error_logging_path = input_path[:-5] + '_errors_logging.json'
        logging.info(f"No error logging path provided, saving errors and warnings to '{error_logging_path}'")
        
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result['revised_node'], f, indent=2, ensure_ascii=False)
    
    with open(error_logging_path, 'w', encoding='utf-8') as f:
        json.dump({'errors': result['errors'], 'warnings': result['warnings']}, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    check_annotation_full()
    
    # Example usage from command line:
    # python annotation_checking.py sun_data/sun_vending.json --output_path sun_data/sun_vending_revised.json --error_logging_path sun_data/sun_vending_errors_logging.json