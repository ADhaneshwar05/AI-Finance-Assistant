def categorize_expense(description):

    description = description.lower()

    if any(word in description for word in [
        "food", "lunch", "dinner", "breakfast",
        "restaurant", "swiggy", "zomato"
    ]):
        return "Food"

    elif any(word in description for word in [
        "uber", "ola", "bus", "metro",
        "train", "taxi", "transport"
    ]):
        return "Transport"

    elif any(word in description for word in [
        "movie", "netflix", "spotify",
        "game", "entertainment"
    ]):
        return "Entertainment"

    elif any(word in description for word in [
        "shirt", "shoes", "clothes",
        "shopping", "amazon", "flipkart"
    ]):
        return "Shopping"

    elif any(word in description for word in [
        "medicine", "doctor", "hospital",
        "pharmacy", "health"
    ]):
        return "Health"

    else:
        return "Other"