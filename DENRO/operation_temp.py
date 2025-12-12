def update_user_profile_with_phone(user_id, first_name, last_name, phone_number=None):
    """Update user profile including phone number."""
    try:
        with connection.cursor() as cur:
            cur.execute("""
                UPDATE users
                SET first_name = %s, last_name = %s, phone_number = %s
                WHERE id = %s;
            """, [first_name, last_name, phone_number, user_id])
        return True, "Profile updated successfully"
    except DatabaseError as e:
        logger.error(f"Error updating user profile: {e}")
        return False, str(e)
