How to use the backtabber:

1. Get the relevant files
	1a. Make the directory data/{year}
	1b. Make "standings.txt", which is tab-separated table
		Columns are "team" and "points"
		Each row is the team's name and their post-r6 points
	1c. For each of rounds 7, 8, 9, make "r{round}_draw.txt"
		Which is a tab-separated table of that round's draw
		Columns are "og", "oo", "cg", and "co"
		Each row is one debate, with the four teams
2. Backtab round 7
	2a. Open round_7_backtab.py and change line 6 to the relevant year
	2b. Run the programme
		Optionally, run a number of other instances simultaneously
		Normal operation has scrolling output, printing current loss
	2c. Read the output in output_{year}.txt
		This is a tab-separated table
		Row (X, 0.2, 0.1, 0, 0.7, 20) means:
			20 simulations have been done
			in 20% of them team X came fourth
			in 10% of them team X came third
			in 70% of them team X came first
		This updates as each simulation comes in
3. Backtab round 8
	3a. Open round_8_backtab.py and change line 6 to the relevant year
	3b. Run the programme
		Again, can run a number of instances simultaneously
		Important note: you need output_{year}.txt in the directory
		Because this is an input for the program
	3c. Read the outputs:
		In the very rare case of hitting zero loss, 
			printed to zero_file.txt, format like r7 backtab
		Sim results saved to expire_file.txt
			Tab-separated, row per (team, round) combination
			Each simulation is saved as a column



This folder contains example outputs, in this case "output_2025.txt", which is the output of the round 7 backtab, and "expire_file.txt", which is the output of the round 8 backtab, all on the 2025 dataset. 

A full writeup of how the program works is in "writeup.pdf".

Warning about data: outside of the 2025 data, there are swing teams around that are debating outside of their bracket. To accommodate them, you can alter the code (specifically the parts that calculate loss) which is not too difficult. 






