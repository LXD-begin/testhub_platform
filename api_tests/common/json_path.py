def get_by_path(data, path):
    current = data
    for part in path.split('.'):
        if part == '':
            continue
        if isinstance(current, list):
            current = current[int(part)]
        else:
            current = current[part]
    return current
