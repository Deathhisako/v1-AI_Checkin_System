.PHONY: install test demo compare run clean

install:
	pip install -r requirements.txt

test:
	python -m unittest discover -s tests -v

demo:
	python main.py --demo 20

compare:
	python main.py --compare 100

run:
	python main.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf logs/*.log 2>/dev/null || true
