import imgkit
import os
import json

# Function to generate HTML table from data
def generate_html_table(data):
    html_table = """
    <style>
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            border: 1px solid #dddddd;
            text-align: left;
            padding: 8px;
        }
        th {
            background-color: #f2f2f2;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
    </style>
    <table>
        <thead>
            <tr>
                <th>Name</th>
                <th>Grade Score</th>
                <th>GPA</th>
                <th>Credit</th>
                <th>Grade Detail</th>
            </tr>
        </thead>
        <tbody>
    """

    for item in data:
        html_table += "<tr>"
        for value in item.values():
            if isinstance(value, list):
                html_table += f"<td>{'<br>'.join(value)}</td>"
            else:
                html_table += f"<td>{value}</td>"
        html_table += "</tr>"

    html_table += """
        </tbody>
    </table>
    """

    return html_table


def generate_img_from_html(data, grades_folder_path):
    # Generate HTML table
    html_table_content = generate_html_table(data)

    # Save HTML content to a file
    with open(os.path.join(grades_folder_path, "grades.html"), "w", encoding="utf-8") as html_file:
        html_file.write(html_table_content)

    # Convert HTML to image using imgkit
    options = {
        'format': 'jpg',
        'encoding': 'utf-8',
    }

    imgkit.from_file(os.path.join(grades_folder_path, "grades.html"), os.path.join(grades_folder_path, "grades.jpg"),
                     options=options)


def generate_grades_to_msg(gardes):
    grades_msg = ""
    for garde in gardes:
        grades_msg += "名称：" + garde["name"] + "\n"
        grades_msg += "分数：" + garde["grade_score"] + "\n"
        grades_msg += "绩点：" + garde["gpa"] + "\n"
        grades_msg += "学分：" + str(garde["credit"]) + "\n"
        grades_msg += "详细成绩:" + "\n"
        for detail in garde["grade_detail"][:-1]:
            grades_msg += "├──" + detail + "\n"
        grades_msg += "└──" + garde["grade_detail"][-1] + "\n\n"
    return grades_msg[:-2]

def get_exams_msg(folder_path):
    with open((os.path.join(folder_path, 'exams.json')), 'r', encoding='utf-8') as f:
        exams = json.loads(f.read())
    exams_msg = ""
    for exam in exams:
        exams_msg += "名称：" + exam["course"] +"\n"
        exams_msg += "地点：" + exam["location"] +"\n"
        exams_msg += "时间：" + exam["time"] +"\n\n"
    exams_msg = exams_msg[:-2]
    return exams_msg