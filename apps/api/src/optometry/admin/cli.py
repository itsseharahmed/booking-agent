"""Interactive CLI for creating administrator accounts."""

from getpass import getpass

from pydantic import EmailStr, TypeAdapter, ValidationError

from optometry.admin.create_admin import create_admin
from optometry.db.session import SessionLocal

email_adapter = TypeAdapter(EmailStr)


def main() -> None:
    print("Create administrator account")

    try:
        email = str(email_adapter.validate_python(input("Admin email: ").strip()))

        password = getpass("Password: ")
        confirmation = getpass("Confirm password: ")

        if password != confirmation:
            print("Error: Passwords do not match.")
            raise SystemExit(1)

        with SessionLocal() as db:
            admin = create_admin(
                db=db,
                email=email,
                password=password,
            )

    except (ValueError, ValidationError) as exc:
        print(f"Error: {exc}")
        raise SystemExit(1) from exc

    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        raise SystemExit(1) from None

    print(f"Administrator created: {admin.email}")


if __name__ == "__main__":
    main()
