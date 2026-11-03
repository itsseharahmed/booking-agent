# interactive CLI for creating administrator accounts.

from getpass import getpass

from pydantic import EmailStr, TypeAdapter, ValidationError

from optometry.admin.create_admin import create_admin
from optometry.db.session import SessionLocal

email_adapter = TypeAdapter(EmailStr)


# handles the main workflow.
def main() -> None:
    print("Create administrator account")

    try:
        # strip email that's entered by user
        email = str(email_adapter.validate_python(input("Admin email: ").strip()))

        # password input without displaying on screen
        password = getpass("Password: ")
        confirmation = getpass("Confirm password: ")

        # check that passwords entered match
        if password != confirmation:
            print("Error: Passwords do not match.")
            raise SystemExit(1)

        # call create_admin function and store to db in a secure connection
        with SessionLocal() as db:
            admin = create_admin(
                db=db,
                email=email,
                password=password,
            )

    # validation error
    except (ValueError, ValidationError) as exc:
        print(f"Error: {exc}")
        raise SystemExit(1) from exc

    # keyboard interrupt
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        raise SystemExit(1) from None

    # if successful
    print(f"Administrator created: {admin.email}")


if __name__ == "__main__":
    main()
