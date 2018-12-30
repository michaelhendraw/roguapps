import datetime

def validate_date(date_text, date_format):
    isValidDate = True
    
    try:
        datetime.datetime.strptime(date_text, date_format)
    except ValueError:
        isValidDate = False

    return isValidDate

def convert_date(date_text, date_format_before, date_format_after):
    return datetime.datetime.strptime(date_text, date_format_before).strftime(date_format_after)

