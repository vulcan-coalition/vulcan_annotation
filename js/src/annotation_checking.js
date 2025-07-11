const fs = require('fs');
const path = require('path');

// Configure logging
function log(level, message) {
    const timestamp = new Date().toISOString();
    console.log(`${timestamp} - ${level} - ${message}`);
}

function checkAnnotation(node, parentPath = '', internalKeyCounter = 0) {
    let errors = [];
    let warnings = [];
    let revisedNode = {};
    
    // first, check if it's a dict in the first place (if not we can't check anything)
    if (typeof node !== 'object' || node === null || Array.isArray(node)) {
        if (!parentPath) {
            errors.push("The input annotation structure is not a dictionary.");
        } else {
            errors.push(`A child node of '${parentPath}' is not a dictionary.`);
        }
        return {'errors': errors, 'warnings': warnings, 'revised_node': null, 'internal_key_counter': internalKeyCounter};
    }
        
    // check 'key' field
    let keyWarning = '';
    let keyHasContent = false;
    let key;
    if (!('key' in node)) {
        internalKeyCounter += 1;
        key = `node_${internalKeyCounter}`;
        if (!parentPath) {
            keyWarning = `The root node is missing key. Assigning a default key: '${key}'.`;
        } else {
            keyWarning = `A child node of '${parentPath}' is missing key. Assigning a default key: '${key}'.`;
        }
    } else {
        if (typeof node['key'] !== 'string') {
            internalKeyCounter += 1;
            key = `node_${internalKeyCounter}`;
            if (!parentPath) {
                keyWarning = `The key of the root node is not a string. Assigning a default key: '${key}'.`;
            } else {
                keyWarning = `The key of a child node of '${parentPath}' is not a string. Assigning a default key: '${key}'.`;
            }
        } else {
            key = node['key'];
            let cleanedKey = key.split('').filter(c => {
                const code = c.charCodeAt(0);
                // Keep printable characters (not control chars), including Unicode
                return code >= 32 && code !== 127; // Remove ASCII control chars and DEL
            }).join('').replace(/\t/g, ' ').replace(/\n/g, ' ').split(/\s+/).filter(s => s.length > 0).join(' ');
            if (cleanedKey !== key) {
                if (cleanedKey === '') {
                    internalKeyCounter += 1;
                    cleanedKey = `node_${internalKeyCounter}`;
                    keyWarning = `The key '${key}' has no content. It has been renamed to '${cleanedKey}'.`;
                } else {
                    keyHasContent = true;
                    keyWarning = `The key '${key}' has been cleaned to '${cleanedKey}' to remove non-printable characters and extra spaces.`;
                }
                key = cleanedKey;
            } else {
                keyHasContent = true;
            }
        }
    }
    if (!(keyHasContent) && !(('description' in node) && typeof node['description'] === 'string' && node['description'].trim())) {
        keyWarning += ` CRITICAL: This node also has no description. Combined with no informative key, it is difficult to understand the purpose of this node.`;
    }
    if (keyWarning) {
        warnings.push(keyWarning);
    }
    revisedNode['key'] = key;
    let fullPath = parentPath ? `${parentPath} -> ${key}` : `${key}`;
    
    // check 'description' field
    if ('description' in node) {
        if (typeof node['description'] !== 'string') {
            warnings.push(`The node '${key}' has a 'description' field that is not a string. (full path to the node: '${fullPath}')`);
        } else {
            let cleanedDescription = node['description'].split('').filter(c => {
                const code = c.charCodeAt(0);
                // Keep printable characters (not control chars), including Unicode
                return code >= 32 && code !== 127; // Remove ASCII control chars and DEL
            }).join('').replace(/\t/g, ' ').replace(/\n/g, ' ').split(/\s+/).filter(s => s.length > 0).join(' ');
            if (cleanedDescription) {
                revisedNode['description'] = cleanedDescription;
            }
        }
    }
                
    // check 'metadata' field
    if (('metadata' in node) && node['metadata']) {
        revisedNode['metadata'] = node['metadata'];
    }
    
    // check 'required' field      
    let required;
    if ('required' in node) {
        if (typeof node['required'] !== 'boolean') {
            if (['True', 'true', 'Yes', 'yes'].includes(node['required'])) {
                warnings.push(`The node '${key}' has a 'required' field in which its value is not a boolean. Assigning 'required': True. (full path to the node: '${fullPath}')`);
                required = true;
            } else {
                warnings.push(`The node '${key}' has a 'required' field in which its value is not a boolean. As a result, the key 'required' is removed from the node, which means the node is assumed to not be required. (full path to the node: '${fullPath}')`);
                required = false;
            }
        } else {
            required = node['required'];
        }
    } else {
        required = false;
    }
    if (required) {
        revisedNode['required'] = true;
    }
    
    // recursively check children
    let children = [];
    if ('choices' in node) {
        if (Array.isArray(node['choices'])) {
            for (let child of node['choices']) {
                let update = checkAnnotation(child, fullPath, internalKeyCounter);
                internalKeyCounter = update['internal_key_counter'];
                errors = errors.concat(update['errors']);
                warnings = warnings.concat(update['warnings']);
                if (update['revised_node'] !== null) {
                    children.push(update['revised_node']);
                }
            }
        } else { // can't do anything with choices that is not a list
            errors.push(`The node '${key}' has the field 'choices' that is not a list. As a result, the key 'choices' is removed from the node, which means it is assumed to have no children. (full path to the node: '${fullPath}')`);
        }
    }
                
    // all children has valid keys now, rename if it's duplicate with either parent or sibling
    for (let i = 0; i < children.length; i++) {
        let childKey = children[i]['key'];
        if ((children.filter(c => c['key'] === childKey).length > 1) || (childKey === key)) {
            // if the key is duplicate with either parent or sibling, rename it
            let originalChildKey = childKey;
            let childKeyCounter = 1;
            childKey = `${childKey}_${childKeyCounter}`;
            while (children.some(c => c['key'] === childKey) || (childKey === key)) {
                childKeyCounter += 1;
                childKey = `${childKey.split('_').slice(0, -1).join('_')}_${childKeyCounter}`;
            }
            if (key === originalChildKey) {
                warnings.push(`The node '${key}' has a child with the same key as itself. Renaming the child to '${childKey}'. (full path to the node: '${fullPath}')`);
            } else {
                warnings.push(`The node '${key}' has a child with the same key as its sibling. Renaming the child from '${originalChildKey}' to '${childKey}'. (full path to the node: '${fullPath}')`);
            }
            children[i]['key'] = childKey;
        }
    }
    
    // check inputType conflicts with children
    let inputType;
    if ('inputType' in node) {
        if (['mutual', 'multiple', 'text', 'property'].includes(node['inputType'])) {
            inputType = node['inputType'];
        } else {
            if (children.length > 0) {
                warnings.push(`The node '${key}' has an invalid inputType. Valid types are 'mutual', 'multiple', 'text', and 'property'. Assigning a default type 'multiple' since it has a child. (full path to the node: '${fullPath}')`);
                inputType = 'multiple';
            } else {
                warnings.push(`The node '${key}' has an invalid inputType. Valid types are 'mutual', 'multiple', 'text', and 'property'. As a result, the key 'inputType' is removed from the node, which means it is assumed to have boolean value of selected/unselected. (full path to the node: '${fullPath}')`);
                inputType = 'boolean';
            }
        }
    } else {
        inputType = 'boolean';
    }
    if (['boolean', 'text'].includes(inputType) && children.length > 0) {
        warnings.push(`The node '${key}' has children but its inputType does not support choices. Valid inputTypes for choices are 'mutual', 'multiple', and 'property'. Assigning a default type 'multiple' since it has a child. (full path to the node: '${fullPath}')`);
        inputType = 'multiple';
    } else if (['mutual', 'multiple', 'property'].includes(inputType) && children.length === 0) {
        warnings.push(`The node '${key}' has inputType '${inputType}' but has no valid child. As a result, the key 'inputType' is removed from the node, which means it is assumed to have boolean value of selected/unselected. (full path to the node: '${fullPath}')`);
        inputType = 'boolean';
    }
    if (!(inputType === 'boolean')) {
        revisedNode['inputType'] = inputType;
    }
    
    // check for requirement conflicts in children   
    for (let child of children) {
        if ('required' in child) { // always required=True, we have already checked it
            if (inputType === 'mutual') { // can't have a required child!
                let childKey = child['key'];
                warnings.push(`The node '${key}' has a child '${childKey}' with required=True, which is not allowed when the inputType of '${key}' is 'mutual'. The child will be set to not required. (full path to the node: '${fullPath}')`);
                delete child['required'];
            } else if (inputType === 'property') { // all children are required by default, just silently remove the 'required' key
                delete child['required'];
            }
        }
    }
    if (children.length === 1) { // valid, just weird
        warnings.push(`The node '${key}' has only one child. It is still valid, but it is recommended to have more than one child, or for it and the child to collapse into one node, for more intuitive annotation structure. (full path to the node: '${fullPath}')`);
    }

    // finally assign children to the revised node
    if (children.length > 0) {
        revisedNode['choices'] = children;
    }
    
    return {'errors': errors, 'warnings': warnings, 'revised_node': revisedNode, 'internal_key_counter': internalKeyCounter};
}

function checkAnnotationFull(inputPath = null, outputPath = null, errorLoggingPath = null) {
    /**
     * Check the annotation structure in the input file and return a revised structure.
     * 
     * Parameters:
     * - inputPath: Path to the input JSON file containing the annotation structure.
     * - outputPath: Path to save the revised annotation structure (optional).
     * - errorLoggingPath: Path to save errors and warnings (optional).
     */

    // Parse command line arguments if no parameters provided
    if (inputPath === null) {
        const args = process.argv.slice(2);
        if (args.length === 0) {
            console.log('Usage: node annotation_checking.js <input_path> [--output_path <output_path>] [--error_logging_path <error_logging_path>]');
            process.exit(1);
        }
        
        inputPath = args[0];
        
        for (let i = 1; i < args.length; i++) {
            if (args[i] === '--output_path' && i + 1 < args.length) {
                outputPath = args[i + 1];
                i++;
            } else if (args[i] === '--error_logging_path' && i + 1 < args.length) {
                errorLoggingPath = args[i + 1];
                i++;
            }
        }
    }
    
    const data = fs.readFileSync(inputPath, 'utf-8');
    const dataDict = JSON.parse(data);
    
    if (typeof dataDict !== 'object' || dataDict === null || Array.isArray(dataDict)) {
        throw new Error("The input annotation structure is not a dictionary.");
    }
    
    const result = checkAnnotation(dataDict);
    
    if (outputPath === null) {
        outputPath = inputPath.slice(0, -5) + '_revised.json';
        log('INFO', `No output path provided, saving revised annotation to '${outputPath}'`);
    }
    if (errorLoggingPath === null) {
        errorLoggingPath = inputPath.slice(0, -5) + '_errors_logging.json';
        log('INFO', `No error logging path provided, saving errors and warnings to '${errorLoggingPath}'`);
    }
        
    fs.writeFileSync(outputPath, JSON.stringify(result['revised_node'], null, 2), 'utf-8');
    
    fs.writeFileSync(errorLoggingPath, JSON.stringify({'errors': result['errors'], 'warnings': result['warnings']}, null, 2), 'utf-8');
}

if (require.main === module) {
    checkAnnotationFull();
    
    // Example usage from command line:
    // node annotation_checking.js sun_data/sun_vending.json --output_path sun_data/sun_vending_revised.json --error_logging_path sun_data/sun_vending_errors_logging.json
}

// Make functions available globally for browser use
window.checkAnnotation = checkAnnotation;
window.checkAnnotationFull = checkAnnotationFull;