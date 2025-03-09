import pandas as pd
import random
from itertools import permutations

# CONFIG
year = 2025
max_search_len = 70
qualifier_loss = 0
cutoff_threshold = 25
cutoff_point = 20
initialise_directory = f"data/{year}"
output_filename = f"output_{year}.txt"


orders = [order for order in permutations([0, 1, 2, 3])]

class Team:
    def __init__(self, name, known):
        self.name = name
        self.known = known
        self.r7_est = 0
        self.r7_room = None # a room here is just a list of four teams
        self.r8_room = None


def initialise(directory):
    """
    Returns three things:
    1. teams (dict): Team objects, key is name
    2. r7_rooms (list): list of rooms, rooms being a list of four Teams
    3. r8_rooms (list): same as r7_rooms, but for round 8
    """
    # Make the teams
    standings = pd.read_csv(f"{directory}/standings.txt", sep="\t")
    teams = {}
    for _, row in standings.iterrows():
        teams[row["team"]] = Team(row["team"], row["points"])

    # Then get r7 info
    r7_draw = pd.read_csv(f"{directory}/r7_draw.txt", sep="\t")
    r7_rooms = []
    for _, row in r7_draw.iterrows():
        room = [teams[name] for name in row]
        r7_rooms.append(room)
        for team in room:
            team.r7_room = room

    # Then get r8 info
    r8_draw = pd.read_csv(f"{directory}/r8_draw.txt", sep="\t")
    r8_rooms = []
    for _, row in r8_draw.iterrows():
        room = [teams[name] for name in row]
        r8_rooms.append(room)
        for team in room:
            team.r8_room = room

    reset_team_results(teams, r7_rooms)

    return teams, r7_rooms, r8_rooms


def reset_team_results(teams, r7_rooms):
    """
    For each r7 room, assign a random result
    If a team isn't in an r7 room, give it a 0
    """
    # Teams that miss r7 get 0
    for team in teams.values():
        if team.r7_room is None:
            team.r7_est = 0

    # Choose a random result per room
    for room in r7_rooms:
        for team, result in zip(room, random.choice(orders)):
            team.r7_est = result


def choose_order_for_r7_room(teams, r7_rooms, r8_rooms, r7_room):
    """
    Runs through each room
    For each possible order, calculates the loss
    Assigns the order with the lowest loss
    """
    team_r8_room = [team.r8_room for team in r7_room
                    if team.r8_room is not None]
        # A list of which r8_rooms the teams end up in
    scores_outside_room = []
        # A list, one element for each room
        # That element is a Series of every team score outside that room
    for room in team_r8_room:
        if room is None:
            scores_outside_room.append(None)
        else:
            scores = pd.Series([t.known + t.r7_est
                                for t in teams.values()
                                if t not in r7_room
                                and t.r8_room is not None])
            scores_outside_room.append(scores)

    best_score = 10**10
    best_order = None
    random.shuffle(orders)
    for order in orders:
        for team, result in zip(r7_room, order):
            team.r7_est = result

        # Get OOB loss: num of teams that fall in between room min and max
        oob_loss = 0
        iters = zip(r7_room, team_r8_room, scores_outside_room)
        for team, room, scores in iters:
            if room is None:
                continue
            room_scores = [t.known + t.r7_est for t in room]
            room_min, room_max = min(room_scores), max(room_scores)
            oob_loss += ((scores > room_min) & (scores < room_max)).sum()

        # Get pullup loss: +1 for each pullup over 4
        pullup_dict = dict(zip(range(28), [0]*28))
        for room in r8_rooms:
            room_max = max([t.known + t.r7_est for t in room])
            for team in room:
                team_points = team.known + team.r7_est
                if team_points < room_max:
                    pullup_dict[team_points] += 1
        pullup_loss = sum([max(0, val - 3) for val in pullup_dict.values()])

        total_loss = oob_loss + pullup_loss
        if total_loss < best_score:
            best_score = total_loss
            best_order = order

    for team, result in zip(r7_room, best_order):
        team.r7_est = result


def global_objective_function(teams, r8_rooms):
    """
    This calculates oob loss and pullup loss across ALL teams
    When this is zero (i.e., a possible r7 result has been found)
    the programme will print to file and go on running simulations
    """
    oob_loss = 0
    post_r7_scores = [team.known + team.r7_est for team in teams.values()
                    if team.r8_room is not None]
    for room in r8_rooms:
        other_scores = [i for i in post_r7_scores]
        room_scores = [team.known + team.r7_est for team in room]
        for room_score in room_scores:
            other_scores.remove(room_score)
        scores = pd.Series(other_scores)
        room_min, room_max = min(room_scores), max(room_scores)
        oob_loss += ((scores > room_min) & (scores < room_max)).sum()

    pullup_loss = 0
    pullup_dict = dict(zip(range(28), [0]*28))
    for room in r8_rooms:
        room_scores = [team.known + team.r7_est for team in room]
        room_max = max(room_scores)
        for team in room:
            if team.known + team.r7_est < room_max:
                pullup_dict[team.known + team.r7_est] += 1
    pullup_loss = sum([max(0, val - 3) for val in pullup_dict.values()])
    return oob_loss, pullup_loss


def make_blank_file(teams, filename):
    """
    Makes the output file
    Want to do this only for the FIRST instance of backtab you launch
    """
    names = [team.name for team in teams.values()]
    df = pd.DataFrame(names, columns=["names"])
    for header in ["0", "1", "2", "3", "count"]:
        df[header] = 0
    open(filename, "w").write(df.to_csv(index=False, sep="\t"))


def file_edit(teams, filename):
    """
    Opens the file, edits it to add a new simulation, closes it
    This means as you generate results, you can check on how they are going
    by going to that file and having a peek, without interrupting the
    programme at all
    Also you can run multiple of this programme in the same directory
    and the odds of them both editing the file and the same time are very
    small, so you can speed up result generation ~4x
    """
    for _ in range(2):
        try:
            last_results = pd.read_csv(filename, sep="\t", index_col=0)
            break
        except FileNotFoundError:
            make_blank_file(teams, filename)
    count = last_results["count"].iloc[0]
    last_results *= count
    for team in teams.values():
        last_results.loc[team.name, f"{team.r7_est}"] += 1
    last_results /= count + 1
    last_results["count"] = count + 1
    open(filename, "w").write(last_results.to_csv(sep="\t"))


def do_sims():
    """
    Run simulations over and over and over
    Can run multiple ones and they will all output to the same file
    """
    teams, r7_rooms, r8_rooms = initialise(initialise_directory)

    i = 0
    while True:
        top = "*" * (13 + len(str(i+1)))
        print(f"{top}\n* FULL RUN {i+1} *\n{top}")
        for j in range(max_search_len):
            print(f"Iteration {j+1}")
            random.shuffle(r7_rooms)
            for r7_room in r7_rooms:
                choose_order_for_r7_room(teams, r7_rooms, r8_rooms, r7_room)
            loss = global_objective_function(teams, r8_rooms)
            print(f"\t{sum(loss)} ({loss})")
            if sum(loss) <= qualifier_loss:
                print("ACHIEVED")
                file_edit(teams, output_filename)
                break
            if sum(loss) > cutoff_threshold and j >= cutoff_point - 1:
                print("CUTOFF FAILED")
                break
            if j == max_search_len - 1:
                print("EXPIRED")
        reset_team_results(teams, r7_rooms)
        i += 1


do_sims()
