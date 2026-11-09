import getpass # python自带模块，用于隐藏输入内容
import pymysql # 链接mysql的库

# 运行时输入 MySQL 用户名和密码
db_user = input("请输入 MySQL 用户名：").strip() # .strip()用于去掉输入密码后的空格
db_password = getpass.getpass("请输入 MySQL 密码：")

# 创建到 eios 数据库的连接
connection = pymysql.connect(
    host="127.0.0.1", # 表示本机端口
    port=3306,
    user=db_user,
    password=db_password,
    database="eios",
    charset="utf8mb4",
    connect_timeout=5,
)

# 使用游标来执行SQL：
# 游标(cursor)是 Python 中用于执行 SQL、获取查询结果的对象
# 在终端中，我们通过SQL语句执行并显示结果
# 在python中，我们通过游标把SQL交给mysql执行，再通过游标取回结果

try:
    # 创建游标，执行查询
    with connection.cursor() as cursor: # 基于上述的连接创建游标，赋给变量cursor
        cursor.execute("SELECT DATABASE(), VERSION()") 
        # cursor.execute执行SQL语句，括号里面是SQL语法
        database_info = cursor.fetchone() 
        # .fetchone()：获取一行结果，赋给database_info fetchall()：取出剩余的所有结果行
        print("当前数据库和服务器版本：", database_info)

        cursor.execute("SELECT COUNT(*) FROM daily_load_summary")
        count_result = cursor.fetchone()
        print("日汇总表当前记录数量：", count_result[0])

finally:
    connection.close()
    print("数据库连接已关闭")