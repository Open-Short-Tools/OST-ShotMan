import argparse
from core import create_new_shot, list_shots, duplicate_shot, delete_shot

parser = argparse.ArgumentParser(description="ShotMan CLI — Manage camera shot .blend files.")

parser.add_argument("--create", metavar="SHOTNAME", help="Create a new shot (e.g. SHOT010)")
parser.add_argument("--list", action="store_true", help="List all existing shot files")
parser.add_argument("--duplicate", metavar="FILENAME", help="Duplicate a shot file (e.g. cam_SHOT010_v01.blend)")
parser.add_argument("--delete", metavar="FILENAME", help="Delete a shot file")

args = parser.parse_args()

if args.create:
    create_new_shot(args.create)

if args.list:
    list_shots()

if args.duplicate:
    duplicate_shot(args.duplicate)

if args.delete:
    delete_shot(args.delete)
